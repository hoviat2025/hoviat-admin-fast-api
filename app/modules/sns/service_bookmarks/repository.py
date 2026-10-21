from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.service import Service, ServiceStatus
from app.models.service_bookmark import ServiceBookmark
from app.models.service_category import ServiceCategory


class ServiceBookmarkRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def add_published(self, bookmarker_id: int, service_id: int) -> bool:
        # Hold a share lock until commit so a concurrent hide/delete cannot
        # invalidate the publication check between validation and insertion.
        published_id = await self.db.scalar(
            select(Service.id)
            .where(Service.id == service_id, Service.status == ServiceStatus.published)
            .with_for_update(read=True)
        )
        if published_id is None:
            return False
        await self.db.execute(
            pg_insert(ServiceBookmark)
            .values(bookmarker_id=bookmarker_id, service_id=service_id)
            .on_conflict_do_nothing(index_elements=["bookmarker_id", "service_id"])
        )
        return True

    async def remove(self, bookmarker_id: int, service_id: int) -> None:
        await self.db.execute(
            delete(ServiceBookmark).where(
                ServiceBookmark.bookmarker_id == bookmarker_id,
                ServiceBookmark.service_id == service_id,
            )
        )

    async def list_published(self, bookmarker_id: int) -> list[Service]:
        result = await self.db.scalars(
            select(Service)
            .join(ServiceBookmark, ServiceBookmark.service_id == Service.id)
            .where(
                ServiceBookmark.bookmarker_id == bookmarker_id,
                Service.status == ServiceStatus.published,
            )
            .options(
                selectinload(Service.contacts),
                selectinload(Service.category_links).selectinload(ServiceCategory.category),
            )
            .order_by(ServiceBookmark.created_at.desc(), ServiceBookmark.service_id.desc())
        )
        return list(result.all())
