# app/modules/hilfen/repositories/news_repository.py
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from app.models.hilfen_news import HilfenNews

logger = logging.getLogger(__name__)

class NewsRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_news(self, user_id: int, **kwargs) -> HilfenNews:
        """Insert a new news row and return it."""
        news = HilfenNews(user_id=user_id, **kwargs)
        self.db.add(news)
        await self.db.flush()
        return news

    async def get_by_id(self, news_id: int) -> HilfenNews | None:
        if not isinstance(news_id, int):
            logger.error(f"get_by_id called with non-int news_id: {news_id!r}")
            return None
        stmt = select(HilfenNews).where(HilfenNews.id == news_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def update_news(self, news_id: int, **kwargs) -> None:
        """
        Update news fields using a direct SQL UPDATE.
        This avoids any ORM dirty‑tracking issues that could flush stale values.
        """
        if not isinstance(news_id, int):
            logger.error(f"update_news called with non-int news_id: {news_id!r}")
            raise TypeError(f"news_id must be int, got {type(news_id).__name__}")

        # Never let the primary key slip into the update
        kwargs.pop("id", None)

        if not kwargs:
            logger.warning("update_news called with no fields to update")
            return

        # Ensure news_text is stored as a string (not int, etc.)
        if "news_text" in kwargs and kwargs["news_text"] is not None:
            kwargs["news_text"] = str(kwargs["news_text"])

        logger.info(f"update_news news_id={news_id}, fields={list(kwargs.keys())}")

        stmt = update(HilfenNews).where(HilfenNews.id == news_id).values(**kwargs)
        await self.db.execute(stmt)

    async def delete_news(self, news_id: int) -> None:
        if not isinstance(news_id, int):
            logger.error(f"delete_news called with non-int news_id: {news_id!r}")
            raise TypeError(f"news_id must be int, got {type(news_id).__name__}")
        stmt = delete(HilfenNews).where(HilfenNews.id == news_id)
        await self.db.execute(stmt)