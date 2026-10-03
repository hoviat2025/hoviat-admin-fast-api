from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin import Admin
from app.models.service import ServiceStatus
from app.modules.admin.audit.repository import AdminAuditRepository
from app.modules.admin.service_management.repositories.service_admin_search import (
    ServiceAdminSearchRepository,
)
from app.modules.admin.service_management.schemas.list_services import ServiceListQuery
from app.modules.services.schemas.category_requests import (
    CategoryCreateRequest,
    CategoryUpdateRequest,
)
from app.modules.services.schemas.category_responses import CategoryResponse
from app.modules.services.schemas.service_requests import (
    ServiceAggregateSaveRequest,
    ServiceCategoriesReplaceRequest,
    ServiceContactsReplaceRequest,
    ServiceCreateRequest,
    ServiceRelevanceUpdate,
    ServiceUpdateRequest,
)
from app.modules.services.schemas.service_responses import ServiceResponse
from app.modules.services.services.category_service import CategoryService
from app.modules.services.services.service_service import ServiceService


class AdminServiceManagementService:
    """
    Admin-facing orchestration over the service-directory domain.

    It re-implements no domain rule. Every validation, the category cycle guard,
    the primary-category check and the provenance uniqueness rule live in the
    Milestone-1 ServiceService / CategoryService. This layer only adds the two
    things specific to an admin operation:

      1. Identity. Authentication and permissions are enforced by the router via
         the shared get_current_admin / require_*_permission dependencies; no
         admin identity is ever taken from the request body.
      2. Audit. An audit row is written through the shared AdminAuditRepository
         in the SAME transaction as the change, using the domain services'
         before_commit hook.

    Ownership stays descriptive data. It is recorded and displayed, but grants no
    edit permission: only admins edit services in this milestone.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.service_domain = ServiceService(db)
        self.category_domain = CategoryService(db)
        self.audit = AdminAuditRepository(db)
        self.search = ServiceAdminSearchRepository(db)

    # ------------------------------------------------------------------ audit

    def _hook(
        self,
        admin: Admin,
        action: str,
        target_type: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        changes: Optional[dict] = None,
        before_values: Optional[dict] = None,
    ):
        """
        Build the before_commit callback handed to the domain service.

        The callback receives the id of the row that was just written, so the
        audit row can point at the real record even for a create. It only
        flushes; the domain service commits afterwards, so the audit row and the
        change land together or not at all.
        """

        async def hook(target_id: int) -> None:
            recorded = changes
            if before_values is not None:
                after = await self.service_domain.get(target_id)
                recorded = {
                    field: {"before": old, "after": getattr(after, field, None)}
                    for field, old in before_values.items()
                    if old != getattr(after, field, None)
                }

            await self.audit.record_action(
                admin_id=admin.id,
                admin_username=admin.username,
                action=action,
                target_type=target_type,
                target_id=target_id,
                changes=recorded or {},
                ip_address=ip_address,
                user_agent=user_agent,
            )

        return hook

    async def _before_values(self, service_id: int, payload) -> dict:
        """
        Snapshot the current values of exactly the fields this payload touches,
        so the audit row can record a real before/after diff.

        The tri-state relevance fields arrive nested under `relevance`, so they
        are flattened here; without this a relevance change made through a
        partial update would be applied but never audited.
        """
        current = await self.service_domain.get(service_id)

        fields = set(payload.model_fields_set)
        relevance = payload.model_fields_set & {"relevance"}
        if relevance:
            fields.discard("relevance")
            fields |= set((payload.relevance or ServiceRelevanceUpdate()).model_fields_set)

        return {
            field: getattr(current, field, None)
            for field in fields
            if hasattr(current, field)
        }

    # ---------------------------------------------------------------- services

    async def create_service(
        self,
        payload: ServiceCreateRequest,
        admin: Admin,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> ServiceResponse:
        return await self.service_domain.create(
            payload,
            before_commit=self._hook(
                admin,
                "service.create",
                "service",
                ip_address,
                user_agent,
                changes={"created": payload.model_dump(mode="json")},
            ),
        )

    async def get_service(self, service_id: int) -> ServiceResponse:
        return await self.service_domain.get(service_id)

    async def save_service(
        self,
        service_id: int,
        payload: ServiceAggregateSaveRequest,
        admin: Admin,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> ServiceResponse:
        """
        The admin editor's save: the whole aggregate in one request, one
        transaction, one audit row.

        The audit record describes the aggregate change as a single action
        rather than one row per field, because that is the unit the admin
        actually performed. It carries the real before/after values: only fields
        that actually changed appear, and contacts and categories are recorded as
        compact before/after representations rather than row counts, so the trail
        shows which specific contact or category changed without dumping every
        row into it.
        """
        before = await self.service_domain.get(service_id)

        async def hook(target_id: int) -> None:
            after = await self.service_domain.get(target_id)
            await self.audit.record_action(
                admin_id=admin.id,
                admin_username=admin.username,
                action="service.save",
                target_type="service",
                target_id=target_id,
                changes=self._aggregate_diff(before, after),
                ip_address=ip_address,
                user_agent=user_agent,
            )

        return await self.service_domain.save_aggregate(
            service_id, payload, before_commit=hook
        )

    # Scalar fields whose value alone is meaningful in an audit trail.
    _AUDITED_SCALARS = (
        "name",
        "description",
        "status",
        "owner_user_id",
        "show_owner",
        "persian_owned",
        "persian_provider",
        "persian_language",
        "persian_service",
        "address",
        "postal_code",
        "city",
        "state",
        "country_code",
        "latitude",
        "longitude",
        "source",
        "external_id",
    )

    def _aggregate_diff(self, before: ServiceResponse, after: ServiceResponse) -> dict:
        """
        Build a compact, meaningful before/after diff of the whole aggregate.

        Scalars are compared by value, so an unchanged field never appears.
        Children are compared as sorted lists of compact representations, so an
        edit that keeps the same number of rows but changes one of them still
        shows up.
        """
        changes: dict = {}

        for field in self._AUDITED_SCALARS:
            old = getattr(before, field, None)
            new = getattr(after, field, None)
            if old != new:
                changes[field] = {"before": old, "after": new}

        contacts_before = self._contacts_signature(before)
        contacts_after = self._contacts_signature(after)
        if contacts_before != contacts_after:
            changes["contacts"] = {"before": contacts_before, "after": contacts_after}

        categories_before = self._categories_signature(before)
        categories_after = self._categories_signature(after)
        if categories_before != categories_after:
            changes["categories"] = {
                "before": categories_before,
                "after": categories_after,
            }

        return changes

    @staticmethod
    def _contacts_signature(service: ServiceResponse) -> list[dict]:
        """
        Compact per-contact representation, sorted so two equal collections
        compare equal. `value` is included because a changed phone number is
        exactly the kind of edit an audit trail exists to show.
        """
        rows = [
            {
                "type": contact.type.value,
                "title": contact.title,
                "value": contact.value,
                "is_visible": contact.is_visible,
            }
            for contact in service.contacts
        ]
        return sorted(rows, key=lambda row: (row["type"], row["value"], row["title"]))

    @staticmethod
    def _categories_signature(service: ServiceResponse) -> list[dict]:
        """
        Compact per-category representation including which one is primary, since
        a change of primary category is a meaningful editorial decision.
        """
        rows = [
            {"category_id": link.category_id, "is_primary": link.is_primary}
            for link in service.categories
        ]
        return sorted(rows, key=lambda row: row["category_id"])

    async def update_service(
        self,
        service_id: int,
        payload: ServiceUpdateRequest,
        admin: Admin,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> ServiceResponse:
        before = await self._before_values(service_id, payload)
        return await self.service_domain.update(
            service_id,
            payload,
            before_commit=self._hook(
                admin,
                "service.update",
                "service",
                ip_address,
                user_agent,
                before_values=before,
            ),
        )

    async def change_status(
        self,
        service_id: int,
        status: ServiceStatus,
        admin: Admin,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> ServiceResponse:
        before = await self.service_domain.get(service_id)
        return await self.service_domain.update(
            service_id,
            ServiceUpdateRequest(status=status),
            before_commit=self._hook(
                admin,
                "service.status_change",
                "service",
                ip_address,
                user_agent,
                changes={
                    "status": {"before": before.status.value, "after": status.value}
                },
            ),
        )

    async def assign_owner(
        self,
        service_id: int,
        owner_user_id: Optional[int],
        admin: Admin,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> ServiceResponse:
        before = await self.service_domain.get(service_id)
        return await self.service_domain.update(
            service_id,
            ServiceUpdateRequest(owner_user_id=owner_user_id),
            before_commit=self._hook(
                admin,
                "service.owner_change",
                "service",
                ip_address,
                user_agent,
                changes={
                    "owner_user_id": {
                        "before": before.owner_user_id,
                        "after": owner_user_id,
                    }
                },
            ),
        )

    async def set_show_owner(
        self,
        service_id: int,
        show_owner: bool,
        admin: Admin,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> ServiceResponse:
        before = await self.service_domain.get(service_id)
        return await self.service_domain.update(
            service_id,
            ServiceUpdateRequest(show_owner=show_owner),
            before_commit=self._hook(
                admin,
                "service.show_owner_change",
                "service",
                ip_address,
                user_agent,
                changes={
                    "show_owner": {"before": before.show_owner, "after": show_owner}
                },
            ),
        )

    async def list_services(self, query: ServiceListQuery):
        """Returns (rows, total) for the router to split into data/meta."""
        return await self.search.search_services(query.to_search_params())

    async def replace_contacts(
        self,
        service_id: int,
        payload: ServiceContactsReplaceRequest,
        admin: Admin,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> ServiceResponse:
        return await self.service_domain.replace_contacts(
            service_id,
            payload,
            before_commit=self._hook(
                admin,
                "service.contacts_change",
                "service",
                ip_address,
                user_agent,
                changes={"contacts": payload.model_dump(mode="json")},
            ),
        )

    async def replace_categories(
        self,
        service_id: int,
        payload: ServiceCategoriesReplaceRequest,
        admin: Admin,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> ServiceResponse:
        return await self.service_domain.replace_categories(
            service_id,
            payload,
            before_commit=self._hook(
                admin,
                "service.categories_change",
                "service",
                ip_address,
                user_agent,
                changes={"categories": payload.model_dump(mode="json")},
            ),
        )

    # ------------------------------------------------------------- categories

    async def list_categories(self, include_inactive: bool = True):
        return await self.category_domain.list(include_inactive=include_inactive)

    async def get_category_tree(self, include_inactive: bool = True):
        return await self.category_domain.tree(include_inactive=include_inactive)

    async def create_category(
        self,
        payload: CategoryCreateRequest,
        admin: Admin,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> CategoryResponse:
        return await self.category_domain.create(
            payload,
            before_commit=self._hook(
                admin,
                "category.create",
                "category",
                ip_address,
                user_agent,
                changes={"created": payload.model_dump(mode="json")},
            ),
        )

    async def update_category(
        self,
        category_id: int,
        payload: CategoryUpdateRequest,
        admin: Admin,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> CategoryResponse:
        before = await self.category_domain.get(category_id)
        before_values = {
            field: getattr(before, field)
            for field in payload.model_fields_set
            if hasattr(before, field)
        }

        async def hook(target_id: int) -> None:
            after = await self.category_domain.get(target_id)
            await self.audit.record_action(
                admin_id=admin.id,
                admin_username=admin.username,
                action="category.update",
                target_type="category",
                target_id=target_id,
                changes={
                    field: {"before": old, "after": getattr(after, field, None)}
                    for field, old in before_values.items()
                    if old != getattr(after, field, None)
                },
                ip_address=ip_address,
                user_agent=user_agent,
            )

        return await self.category_domain.update(
            category_id, payload, before_commit=hook
        )
