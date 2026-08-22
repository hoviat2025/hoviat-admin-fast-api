from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.models.user import User


class UserLookupRepository:
    """
    Handles database queries related to fetching specific user entities.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id_with_privacy(self, user_id: int) -> User | None:
        """
        Fetches a User by ID and eagerly loads their privacy settings and social
        links. Returns None if the user does not exist.
        """
        stmt = (
            select(User)
            .options(
                joinedload(User.privacy_settings),
                selectinload(User.social_links),
            )
            .where(User.user_id == user_id)
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()
