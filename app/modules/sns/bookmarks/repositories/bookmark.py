from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bookmark import Bookmark


class BookmarkRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def add(self, bookmarker_id: int, bookmarked_user_id: int) -> None:
        """
        Save a bookmark. Idempotent: re-saving an existing bookmark is a no-op.
        """
        stmt = (
            pg_insert(Bookmark)
            .values(
                bookmarker_id=bookmarker_id,
                bookmarked_user_id=bookmarked_user_id,
            )
            .on_conflict_do_nothing(
                index_elements=["bookmarker_id", "bookmarked_user_id"]
            )
        )
        await self.db.execute(stmt)

    async def remove(self, bookmarker_id: int, bookmarked_user_id: int) -> None:
        """
        Remove a bookmark. Idempotent: removing a non-existent bookmark is a no-op.
        """
        stmt = delete(Bookmark).where(
            Bookmark.bookmarker_id == bookmarker_id,
            Bookmark.bookmarked_user_id == bookmarked_user_id,
        )
        await self.db.execute(stmt)

    async def list_ids(self, bookmarker_id: int) -> list[int]:
        stmt = (
            select(Bookmark.bookmarked_user_id)
            .where(Bookmark.bookmarker_id == bookmarker_id)
            .order_by(Bookmark.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return [row[0] for row in result.all()]
