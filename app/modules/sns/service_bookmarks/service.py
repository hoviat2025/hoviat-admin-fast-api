from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ServiceError
from app.modules.services.public.serialization import to_public_service
from app.modules.services.schemas.public_service_responses import PublicServiceResponse
from app.modules.sns.service_bookmarks.repository import ServiceBookmarkRepository


class ServiceBookmarkService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repository = ServiceBookmarkRepository(db)

    async def save(self, bookmarker_id: int, service_id: int) -> None:
        try:
            if not await self.repository.add_published(bookmarker_id, service_id):
                # Hidden and missing listings are indistinguishable.
                raise ServiceError("SERVICE_NOT_FOUND", "Service not found", 404)
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            raise

    async def remove(self, bookmarker_id: int, service_id: int) -> None:
        try:
            # Also allow removal after a business has become hidden or deleted.
            await self.repository.remove(bookmarker_id, service_id)
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            raise

    async def list(self, bookmarker_id: int) -> tuple[list[PublicServiceResponse], int]:
        rows = await self.repository.list_published(bookmarker_id)
        items = [to_public_service(row) for row in rows]
        return items, len(items)
