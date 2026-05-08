import logging
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.shared.repositories.user_base import UserBaseRepository  # generic repo

logger = logging.getLogger(__name__)


class BanService:
    """Handles ban/unban and ban‑status checks for users."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = UserBaseRepository(db)

    async def is_banned(self, user: User) -> bool:
        """Return True if the user is currently banned."""
        return bool(user.is_ban)  # assuming is_ban is a boolean column

    async def ban_user(self, user_id: int) -> None:
        """Mark the user as banned."""
        user = await self.repo.get_by_id(user_id)
        if user:
            user.is_ban = True
            await self.db.flush()
            logger.info(f"User {user_id} banned.")
        else:
            logger.warning(f"Attempt to ban non‑existent user {user_id}.")

    async def unban_user(self, user_id: int) -> None:
        """Remove the ban from the user."""
        user = await self.repo.get_by_id(user_id)
        if user:
            user.is_ban = False
            await self.db.flush()
            logger.info(f"User {user_id} unbanned.")
        else:
            logger.warning(f"Attempt to unban non‑existent user {user_id}.")