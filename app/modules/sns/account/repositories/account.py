from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.user import User
from app.shared.repositories.user_base import UserBaseRepository


class AccountRepository(UserBaseRepository):
    """
    Extends the shared user repository with SNS-account specific lookups.
    """

    async def get_full(self, user_id: int) -> User | None:
        """
        Fetch a user with privacy settings and social links eagerly loaded.
        """
        stmt = (
            select(User)
            .where(User.user_id == user_id)
            .options(
                selectinload(User.privacy_settings),
                selectinload(User.social_links),
            )
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()
