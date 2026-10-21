"""Owner authorization around the existing transactional service domain."""

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.core.exceptions import ServiceError
from app.models.service import Service
from app.models.service_category import ServiceCategory
from app.modules.services.schemas.service_requests import (
    ServiceAggregateSaveRequest,
    ServiceCreateRequest,
)
from app.modules.services.services.service_service import ServiceService
from app.modules.sns.owned_services.schemas import (
    OwnedServiceResponse,
    OwnedServiceUpdateRequest,
)


class OwnedServiceService:
    def __init__(self, db):
        self.db = db
        self.domain = ServiceService(db)

    def _owned_rows(self, user_id: int):
        # Authorize the freshly fetched parent and eagerly load its children.
        # Shared row locks prevent reassignment while those subsequent queries
        # load private contacts. They last until the request session closes.
        return (
            select(Service)
            .where(Service.owner_user_id == user_id)
            .execution_options(populate_existing=True)
            .options(
                selectinload(Service.contacts),
                selectinload(Service.category_links).selectinload(
                    ServiceCategory.category
                ),
            )
            .with_for_update(read=True)
        )

    async def list(self, user_id: int, page: int, size: int):
        total = await self.db.scalar(
            select(func.count()).select_from(Service).where(
                Service.owner_user_id == user_id
            )
        )
        result = await self.db.execute(
            self._owned_rows(user_id)
            .order_by(Service.id.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
        items = self.domain.serialize_services(result.scalars().all())
        return [OwnedServiceResponse.from_service(item) for item in items], int(total or 0)

    async def _require_owner(self, user_id: int, service_id: int, *, lock=False):
        repository = self.domain.services
        row = await (
            repository.get_for_update(service_id)
            if lock else repository.get(service_id)
        )
        # Use the same response for an unknown id and another person's listing.
        if row is None or row.owner_user_id != user_id:
            raise ServiceError("SERVICE_NOT_FOUND", "Service not found", 404)
        return row

    async def get(self, user_id: int, service_id: int):
        result = await self.db.execute(
            self._owned_rows(user_id).where(Service.id == service_id)
        )
        row = result.scalars().first()
        if row is None:
            raise ServiceError("SERVICE_NOT_FOUND", "Service not found", 404)
        service = self.domain.serialize_services([row])[0]
        return OwnedServiceResponse.from_service(service)

    async def update(
        self, user_id: int, service_id: int, payload: OwnedServiceUpdateRequest
    ):
        # Keep the authorization row locked until the domain's single commit.
        # An admin cannot reassign the listing between this check and the save.
        await self._require_owner(user_id, service_id, lock=True)
        current = await self.domain.get(service_id)

        # Preserve staff-controlled fields from the locked record. Owners cannot
        # assign themselves a listing, publish it, or edit its provenance or
        # category/relevance assessments through this request schema.
        aggregate = current.model_dump(include=set(ServiceCreateRequest.model_fields))
        aggregate["contacts"] = [
            item.model_dump(exclude={"id"}) for item in current.contacts
        ]
        aggregate["categories"] = [
            item.model_dump(include={"category_id", "is_primary"})
            for item in current.categories
        ]
        aggregate.update(payload.model_dump(exclude_unset=True, exclude={"owner_show_profile"}))

        await self.domain.save_aggregate(
            service_id, ServiceAggregateSaveRequest.model_validate(aggregate),
            owner_show_profile=payload.owner_show_profile,
        )
        # The domain commits before reading its result. Ownership might change
        # after that commit; authorize a fresh, locked read before returning any
        # private business contacts to this user.
        return await self.get(user_id, service_id)
