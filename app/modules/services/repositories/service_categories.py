from typing import Sequence

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.service import Service, ServiceStatus
from app.models.service_category import ServiceCategory


class ServiceCategoryRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_by_service(self, service_id: int) -> Sequence[ServiceCategory]:
        stmt = (
            select(ServiceCategory)
            .where(ServiceCategory.service_id == service_id)
            .options(selectinload(ServiceCategory.category))
            .order_by(ServiceCategory.is_primary.desc(), ServiceCategory.category_id)
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def published_services_with_primary(
        self, category_id: int
    ) -> Sequence[tuple[int, str]]:
        """
        Services that are published AND use this category as their primary one.

        Used to refuse deactivating such a category: retiring it would leave
        public pages pointing at a category the product says cannot be primary.
        Returns (service_id, service_name) so the error can name them.
        """
        result = await self.db.execute(
            select(Service.id, Service.name)
            .join(
                ServiceCategory,
                (ServiceCategory.service_id == Service.id)
                & (ServiceCategory.category_id == category_id)
                & ServiceCategory.is_primary.is_(True),
            )
            .where(Service.status == ServiceStatus.published)
            .order_by(Service.id)
        )
        return result.all()

    async def replace(self, service_id: int, links: list[dict]) -> None:
        """
        Replace all category assignments for a service.

        `links` items are {category_id, is_primary}. Duplicate category ids are
        collapsed (the table's primary key would reject them otherwise), and at
        most one primary is kept. The primary constraint is also enforced by a
        partial unique index in the database.
        """
        await self.db.execute(
            delete(ServiceCategory).where(ServiceCategory.service_id == service_id)
        )

        seen: set[int] = set()
        primary_taken = False

        for link in links:
            category_id = int(link["category_id"])
            if category_id in seen:
                continue
            seen.add(category_id)

            is_primary = bool(link.get("is_primary"))
            if is_primary and primary_taken:
                is_primary = False
            if is_primary:
                primary_taken = True

            self.db.add(
                ServiceCategory(
                    service_id=service_id,
                    category_id=category_id,
                    is_primary=is_primary,
                )
            )
