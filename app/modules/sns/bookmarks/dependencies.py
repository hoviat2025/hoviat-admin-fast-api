from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.sns.bookmarks.services.bookmark_service import BookmarkService


def get_bookmark_service(db: AsyncSession = Depends(get_db)) -> BookmarkService:
    """
    Dependency injection factory for the SNS bookmarks feature.
    """
    return BookmarkService(db)
