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
    ServiceCategoriesReplaceRequest,
    ServiceContactsReplaceRequest,
    ServiceCreateRequest,
    ServiceUpdateRequest,
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
        category_id: Optional[int] = None,
        status: Optional[ServiceStatus] = None,
        persian_owned: Optional[bool] = None,
        persian_language: Optional[bool] = None,
        persian_service: Optional[bool] = None,
        owner_user_id: Optional[int] = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[ServiceResponse], int]:
        rows, total = await self.services.list(
            q=q,
            city=city,
            category_id=category_id,
            status=status.value if status is not None else None,
            persian_owned=persian_owned,
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
        resolve_primary_category(pairs)
        validate_category_selection(pairs, payload.status)
        await self._ensure_categories_exist(pairs)

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
                "persian_owned": payload.persian_owned,
                "persian_language": payload.persian_language,
                "persian_service": payload.persian_service,
                "address": clean_optional_text(payload.address),
                "postal_code": clean_optional_text(payload.postal_code),
                "city": clean_optional_text(payload.city),
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

        if "name" in data:
            data["name"] = require_non_empty(data["name"], "name")

        for field in ("description", "address", "postal_code", "city", "country"):
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
        if "status" in data and data["status"] is not None:
            links = await self.category_links.list_by_service(service_id)
            pairs = [(link.category_id, link.is_primary) for link in links]
            validate_category_selection(pairs, data["status"])

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
        service = await self.services.get(service_id)
        if not service:
            raise ServiceError("SERVICE_NOT_FOUND", "Service not found", 404)

        await self.contacts.replace(
            service_id, [self._contact_to_dict(item) for item in payload.contacts]
        )
        await self._finish(before_commit, service_id)
        return await self.get(service_id)

    async def replace_categories(
        self,
        service_id: int,
        payload: ServiceCategoriesReplaceRequest,
        *,
        before_commit: Optional[BeforeCommit] = None,
    ) -> ServiceResponse:
        service = await self.services.get(service_id)
        if not service:
            raise ServiceError("SERVICE_NOT_FOUND", "Service not found", 404)

        pairs = self._pairs_from_input(payload.categories)
        resolve_primary_category(pairs)
        validate_category_selection(pairs, service.status)
        await self._ensure_categories_exist(pairs)

        await self.category_links.replace(service_id, self._link_dicts(pairs))
        await self._finish(before_commit, service_id)
        return await self.get(service_id)

    # ------------------------------------------------------------- internals

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
            persian_owned=service.persian_owned,
            persian_language=service.persian_language,
            persian_service=service.persian_service,
            address=service.address,
            postal_code=service.postal_code,
            city=service.city,
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
