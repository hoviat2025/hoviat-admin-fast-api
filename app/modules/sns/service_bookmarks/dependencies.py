from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.sns.service_bookmarks.service import ServiceBookmarkService


def get_service_bookmark_service(
    db: AsyncSession = Depends(get_db),
) -> ServiceBookmarkService:
    return ServiceBookmarkService(db)
