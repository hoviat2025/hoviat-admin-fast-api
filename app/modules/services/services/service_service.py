from __future__ import annotations

from typing import Awaitable, Callable, Optional, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ServiceError
from app.models.service import Service, ServiceStatus
from app.modules.services.repositories.category import CategoryRepository
from app.modules.services.repositories.contacts import ServiceContactRepository
from app.modules.services.repositories.service import ServiceRepository
from app.modules.services.repositories.service_categories import (
    ServiceCategoryRepository,
)
from app.modules.services.schemas.category_responses import CategorySummaryResponse
from app.modules.services.schemas.service_requests import (
    ServiceAggregateSaveRequest,
    ServiceCategoriesReplaceRequest,
    ServiceContactsReplaceRequest,
    ServiceCreateRequest,
    ServiceUpdateRequest,
    TriStateFilter,
)
from app.modules.services.schemas.service_responses import (
    ServiceCategoryResponse,
    ServiceContactResponse,
    ServiceResponse,
)
from app.modules.services.validation import (
    clean_optional_text,
    require_non_empty,
    resolve_primary_category,
    updated_at_conflicts,
    validate_category_assignments,
    validate_category_selection,
    validate_contact_fields,
    validate_latitude,
    validate_location_pair,
    validate_longitude,
    validate_provenance,
)
from app.shared.repositories.user_base import UserBaseRepository

# Invoked immediately before the transaction is committed, with the id of the
# row that was just written. It lets the admin layer write an audit-log row in
# the same transaction as the change, without this domain layer knowing
# anything about admins.
BeforeCommit = Callable[[int], Awaitable[None]]


class ServiceService:
    """
    Business logic for service listings.

    There are no HTTP routes in this milestone; the admin endpoints (Milestone
    2) and the public search (Milestone 4) will call these methods. Validation
    lives here and in app.modules.services.validation, so every entry point —
    admin form, importer, seed script — is checked the same way.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.services = ServiceRepository(db)
        self.categories = CategoryRepository(db)
        self.contacts = ServiceContactRepository(db)
        self.category_links = ServiceCategoryRepository(db)
        self.users = UserBaseRepository(db)

    # ------------------------------------------------------------------ reads

    def serialize_services(self, rows: Sequence[Service]) -> list[ServiceResponse]:
        """
        Build response models from already-loaded Service rows.

        Rows must have their contacts and category links eagerly loaded; the
        mapper otherwise triggers a lazy load outside the async context, which
        raises MissingGreenlet during response serialization.
        """
        return [self._to_response(row) for row in rows]

    async def get(self, service_id: int) -> ServiceResponse:
        service = await self.services.get_full(service_id)
        if not service:
            raise ServiceError("SERVICE_NOT_FOUND", "Service not found", 404)
        return self._to_response(service)

    async def list(
        self,
        q: Optional[str] = None,
        city: Optional[str] = None,
        state: Optional[str] = None,
        category_id: Optional[int] = None,
        status: Optional[ServiceStatus] = None,
        persian_owned: Optional[TriStateFilter] = None,
        persian_provider: Optional[TriStateFilter] = None,
        persian_language: Optional[TriStateFilter] = None,
        persian_service: Optional[TriStateFilter] = None,
        owner_user_id: Optional[int] = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[ServiceResponse], int]:
        rows, total = await self.services.list(
            q=q,
            city=city,
            state=state,
            category_id=category_id,
            status=status.value if status is not None else None,
            persian_owned=persian_owned,
            persian_provider=persian_provider,
            persian_language=persian_language,
            persian_service=persian_service,
            owner_user_id=owner_user_id,
            page=page,
            size=size,
        )
        return [self._to_response(row) for row in rows], total

    # ----------------------------------------------------------------- writes

    async def create(
        self,
        payload: ServiceCreateRequest,
        *,
        before_commit: Optional[BeforeCommit] = None,
    ) -> ServiceResponse:
        name = require_non_empty(payload.name, "name")

        validate_location_pair(payload.latitude, payload.longitude)
        latitude = validate_latitude(payload.latitude)
        longitude = validate_longitude(payload.longitude)

        source, external_id = validate_provenance(payload.source, payload.external_id)

        pairs = self._pairs_from_input(payload.categories)
        await self._validate_category_state(
            pairs, service_id=None, resulting_status=payload.status
        )

        if payload.owner_user_id is not None:
            await self._ensure_owner_exists(payload.owner_user_id)

        if source is not None and external_id is not None:
            if await self.services.exists_external(source, external_id):
                raise ServiceError(
                    "CONFLICT_OCCURRED",
                    "a service with this source and external_id already exists",
                    409,
                )

        service = await self.services.create(
            {
                "name": name,
                "description": clean_optional_text(payload.description),
                "owner_user_id": payload.owner_user_id,
                "show_owner": payload.show_owner,
                # Tri-state: an unassessed signal stays null rather than
                # defaulting to False, so the record does not claim to have
                # been checked when nobody checked it.
                "persian_owned": payload.persian_owned,
                "persian_provider": payload.persian_provider,
                "persian_language": payload.persian_language,
                "persian_service": payload.persian_service,
                "address": clean_optional_text(payload.address),
                "postal_code": clean_optional_text(payload.postal_code),
                "city": clean_optional_text(payload.city),
                "state": clean_optional_text(payload.state),
                "country": clean_optional_text(payload.country),
                "latitude": latitude,
                "longitude": longitude,
                "status": payload.status,
                "source": source,
                "external_id": external_id,
            }
        )

        await self.contacts.replace(
            service.id, [self._contact_to_dict(item) for item in payload.contacts]
        )
        await self.category_links.replace(service.id, self._link_dicts(pairs))

        await self._finish(before_commit, service.id)
        return await self.get(service.id)

    async def update(
        self,
        service_id: int,
        payload: ServiceUpdateRequest,
        *,
        before_commit: Optional[BeforeCommit] = None,
    ) -> ServiceResponse:
        service = await self.services.get(service_id)
        if not service:
            raise ServiceError("SERVICE_NOT_FOUND", "Service not found", 404)

        data = payload.model_dump(exclude_unset=True)

        # The tri-state relevance values arrive nested so that a partial update
        # can say "set this one to unknown" (explicit null) while leaving the
        # other three alone. exclude_unset recurses, so the nested dict holds
        # exactly the keys the admin sent: absent = untouched, null = unknown.
        relevance = data.pop("relevance", None)
        if relevance is not None:
            data.update(relevance)

        if "name" in data:
            data["name"] = require_non_empty(data["name"], "name")

        for field in (
            "description",
            "address",
            "postal_code",
            "city",
            "state",
            "country",
        ):
            if field in data:
                data[field] = clean_optional_text(data[field])

        # Coordinates must be validated as the resulting pair, not just the
        # supplied half.
        if "latitude" in data or "longitude" in data:
            latitude = data.get("latitude", service.latitude)
            longitude = data.get("longitude", service.longitude)
            validate_location_pair(latitude, longitude)
            data["latitude"] = validate_latitude(latitude)
            data["longitude"] = validate_longitude(longitude)

        if "owner_user_id" in data and data["owner_user_id"] is not None:
            await self._ensure_owner_exists(data["owner_user_id"])

        # Provenance is validated as the resulting pair, not just the supplied
        # half, so an admin can correct one field, clear both, or set both.
        if "source" in data or "external_id" in data:
            source = data.get("source", service.source)
            external_id = data.get("external_id", service.external_id)
            source, external_id = validate_provenance(source, external_id)
            if source is not None and external_id is not None:
                if await self.services.exists_external(
                    source, external_id, exclude_service_id=service_id
                ):
                    raise ServiceError(
                        "CONFLICT_OCCURRED",
                        "another service already uses this source and external_id",
                        409,
                    )
            data["source"] = source
            data["external_id"] = external_id

        # Publishing requires categories; check against the ones already set.
        # This goes through _validate_category_state rather than the count-only
        # check, because publishing also requires the primary category to be
        # active. Using the weaker check here would let a service whose primary
        # category has been retired be published, bypassing the rule the
        # aggregate save enforces. It also locks those category rows, so a
        # concurrent deactivation cannot slip between this check and the commit.
        if "status" in data and data["status"] is not None:
            links = await self.category_links.list_by_service(service_id)
            pairs = [(link.category_id, link.is_primary) for link in links]
            await self._validate_category_state(
                pairs, service_id=service_id, resulting_status=data["status"]
            )

        await self.services.update(service_id, data)
        await self._finish(before_commit, service_id)
        return await self.get(service_id)

    async def replace_contacts(
        self,
        service_id: int,
        payload: ServiceContactsReplaceRequest,
        *,
        before_commit: Optional[BeforeCommit] = None,
    ) -> ServiceResponse:
        # Lock the parent row for the same reason the aggregate save does:
        # replacing children without holding the parent lock lets a concurrent
        # aggregate save interleave, producing a service whose contacts and
        # categories come from two different saves.
        service = await self.services.get_for_update(service_id)
        if not service:
            raise ServiceError("SERVICE_NOT_FOUND", "Service not found", 404)

        await self.contacts.replace(
            service_id, [self._contact_to_dict(item) for item in payload.contacts]
        )
        # Child-only change: move the parent's updated_at (see save_aggregate).
        await self.services.touch(service_id)
        await self._finish(before_commit, service_id)
        return await self.get(service_id)

    async def replace_categories(
        self,
        service_id: int,
        payload: ServiceCategoriesReplaceRequest,
        *,
        before_commit: Optional[BeforeCommit] = None,
    ) -> ServiceResponse:
        # Lock the parent before replacing children, so this cannot interleave with a
        # concurrent aggregate save of the same service.
        service = await self.services.get_for_update(service_id)
        if not service:
            raise ServiceError("SERVICE_NOT_FOUND", "Service not found", 404)

        pairs = self._pairs_from_input(payload.categories)
        await self._validate_category_state(
            pairs, service_id=service_id, resulting_status=service.status
        )

        await self.category_links.replace(service_id, self._link_dicts(pairs))
        # Child-only change: move the parent's updated_at so it keeps describing
        # the aggregate and stays usable as a version token.
        await self.services.touch(service_id)
        await self._finish(before_commit, service_id)
        return await self.get(service_id)

    # ------------------------------------------------- aggregate save (admin)

    async def save_aggregate(
        self,
        service_id: int,
        payload: ServiceAggregateSaveRequest,
        *,
        before_commit: Optional[BeforeCommit] = None,
    ) -> ServiceResponse:
        """
        Replace the complete editable state of an existing service in ONE
        transaction.

        This is what the admin editor uses. The previous flow issued four to five
        separately committed requests, so a failure halfway left a service with
        new contacts but old categories, or a new status with a stale primary
        category. Everything below is validated first, then written, then
        committed once.

        Concurrency: the row is locked with SELECT ... FOR UPDATE, so two
        concurrent saves serialise. On top of that, `expected_updated_at` gives
        optimistic detection: if the row moved on since the editor loaded it, the
        save is refused with 409 rather than silently overwriting the other admin.
        """
        # 1. Lock the row; this serialises concurrent writers.
        service = await self.services.get_for_update(service_id)
        if not service:
            raise ServiceError("SERVICE_NOT_FOUND", "Service not found", 404)

        # 2. Optimistic concurrency check against the editor's loaded version.
        if updated_at_conflicts(service.updated_at, payload.expected_updated_at):
            raise ServiceError(
                "CONFLICT_OCCURRED",
                "this service was changed by someone else; reload it before saving again",
                409,
            )

        # 3. Validate the complete resulting state before touching anything.
        name = require_non_empty(payload.name, "name")
        validate_location_pair(payload.latitude, payload.longitude)
        latitude = validate_latitude(payload.latitude)
        longitude = validate_longitude(payload.longitude)
        source, external_id = validate_provenance(
            payload.source, payload.external_id
        )

        if payload.owner_user_id is not None:
            await self._ensure_owner_exists(payload.owner_user_id)

        if (
            source is not None
            and external_id is not None
            and await self.services.exists_external(
                source, external_id, exclude_service_id=service_id
            )
        ):
            raise ServiceError(
                "CONFLICT_OCCURRED",
                "another service already uses this source and external_id",
                409,
            )

        pairs = self._pairs_from_input(payload.categories)
        await self._validate_category_state(
            pairs, service_id=service_id, resulting_status=payload.status
        )

        # 4. Children first, parent last: the parent's updated_at must reflect
        #    the final state of the aggregate.
        await self.contacts.replace(
            service_id, [self._contact_to_dict(item) for item in payload.contacts]
        )
        await self.category_links.replace(service_id, self._link_dicts(pairs))

        await self.services.update(
            service_id,
            {
                "name": name,
                "description": clean_optional_text(payload.description),
                "owner_user_id": payload.owner_user_id,
                "show_owner": payload.show_owner,
                # Tri-state relevance: None is a meaningful "not assessed" and
                # is stored as null, not coerced to False.
                "persian_owned": payload.persian_owned,
                "persian_provider": payload.persian_provider,
                "persian_language": payload.persian_language,
                "persian_service": payload.persian_service,
                "address": clean_optional_text(payload.address),
                "postal_code": clean_optional_text(payload.postal_code),
                "city": clean_optional_text(payload.city),
                "state": clean_optional_text(payload.state),
                "country": clean_optional_text(payload.country),
                "latitude": latitude,
                "longitude": longitude,
                "status": payload.status,
                "source": source,
                "external_id": external_id,
            },
        )

        await self._finish(before_commit, service_id)
        return await self.get(service_id)

    # ------------------------------------------------------------- internals

    async def _validate_category_state(
        self,
        pairs: Sequence[tuple[int, bool]],
        *,
        service_id: Optional[int],
        resulting_status: ServiceStatus,
    ) -> None:
        """
        Full category-rule check for a write: existence, at-most-one-primary,
        publish requirements, and the retired (inactive) category rules.

        The categories involved are read under an exclusive row lock, which is
        what makes "a published service must have an active primary category"
        hold against a concurrent category deactivation: the deactivation path
        locks the same rows before deciding, so the two operations serialise and
        the one that loses re-reads committed state and refuses.
        """
        resolve_primary_category(pairs)
        validate_category_selection(pairs, resulting_status)

        requested = [category_id for category_id, _ in pairs]
        if not requested:
            return

        activity = await self.categories.locked_activity_map(requested)
        missing = set(requested) - set(activity)
        if missing:
            raise ServiceError(
                "CATEGORY_NOT_FOUND",
                "Unknown category id(s): "
                + ", ".join(str(x) for x in sorted(missing)),
                404,
            )

        currently_assigned: set[int] = set()
        current_primary_id: Optional[int] = None
        if service_id is not None:
            links = await self.category_links.list_by_service(service_id)
            currently_assigned = {link.category_id for link in links}
            current_primary_id = next(
                (link.category_id for link in links if link.is_primary), None
            )

        validate_category_assignments(
            pairs,
            active_by_id=activity,
            currently_assigned=currently_assigned,
            current_primary_id=current_primary_id,
            status=resulting_status,
        )

    async def _finish(
        self, before_commit: Optional[BeforeCommit], target_id: int
    ) -> None:
        """
        Run the caller's hook, then commit. The hook runs last so anything it
        records (an admin audit row, for example) is part of the same
        transaction as the change itself.
        """
        if before_commit is not None:
            await before_commit(target_id)
        await self.db.commit()

    @staticmethod
    def _pairs_from_input(items: Sequence) -> list[tuple[int, bool]]:
        return [(int(item.category_id), bool(item.is_primary)) for item in items]

    @staticmethod
    def _link_dicts(pairs: Sequence[tuple[int, bool]]) -> list[dict]:
        return [
            {"category_id": category_id, "is_primary": is_primary}
            for category_id, is_primary in pairs
        ]

    @staticmethod
    def _contact_to_dict(item) -> dict:
        title, value = validate_contact_fields(item.title, item.value)
        return {
            "title": title,
            "type": item.type,
            "value": value,
            "platform": clean_optional_text(item.platform),
            "display_order": item.display_order,
            "is_visible": item.is_visible,
        }

    async def _ensure_categories_exist(
        self, pairs: Sequence[tuple[int, bool]]
    ) -> None:
        requested = {category_id for category_id, _ in pairs}
        if not requested:
            return
        found = await self.categories.exists(list(requested))
        missing = requested - found
        if missing:
            raise ServiceError(
                "CATEGORY_NOT_FOUND",
                "Unknown category id(s): " + ", ".join(str(x) for x in sorted(missing)),
                404,
            )

    async def _ensure_owner_exists(self, user_id: int) -> None:
        if not await self.users.get_by_id(user_id):
            raise ServiceError("USER_NOT_FOUND", "Owner user not found", 404)

    def _to_response(self, service: Service) -> ServiceResponse:
        return ServiceResponse(
            id=service.id,
            owner_user_id=service.owner_user_id,
            show_owner=service.show_owner,
            name=service.name,
            description=service.description,
            # Tri-state Iranian/Persian relevance. None means "not assessed"
            # and must survive to the response instead of collapsing to False.
            persian_owned=service.persian_owned,
            persian_provider=service.persian_provider,
            persian_language=service.persian_language,
            persian_service=service.persian_service,
            address=service.address,
            postal_code=service.postal_code,
            city=service.city,
            state=service.state,
            country=service.country,
            latitude=service.latitude,
            longitude=service.longitude,
            status=service.status,
            source=service.source,
            external_id=service.external_id,
            created_at=service.created_at,
            updated_at=service.updated_at,
            contacts=[
                ServiceContactResponse.model_validate(contact)
                for contact in service.contacts
            ],
            categories=[
                ServiceCategoryResponse(
                    category_id=link.category_id,
                    is_primary=link.is_primary,
                    category=(
                        CategorySummaryResponse.model_validate(link.category)
                        if link.category is not None
                        else None
                    ),
                )
                for link in service.category_links
            ],
        )
