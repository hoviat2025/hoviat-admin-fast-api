# app\modules\hilfen\repositories\user_repository.py
"""
HilfenUserRepository

This repository wraps the shared UserBaseRepository. It exists to keep the
Hilfen module decoupled from other modules should user management evolve
independently in the future.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update
from app.shared.repositories.user_base import UserBaseRepository


class HilfenUserRepository(UserBaseRepository):
    """
    Thin wrapper around UserBaseRepository.

    This class exists so the Hilfen module does not depend directly on
    the shared user repository structure and can introduce Hilfen-specific
    user logic later without changing other modules.
    """

    def __init__(self, db: AsyncSession):
        super().__init__(db)

    async def update_first_name(self, user_id: int, first_name: str) -> None:
        """Update user's first name."""
        stmt = (
            update(self.model)
            .where(self.model.user_id == user_id)
            .values(first_name=first_name)
        )
        await self.db.execute(stmt)

    async def update_field(self, user_id: int, field_name: str, value: any) -> None:
        """Update a specific field for a user."""
        update_data = {field_name: value}
        stmt = (
            update(self.model)
            .where(self.model.user_id == user_id)
            .values(**update_data)
        )
        await self.db.execute(stmt)

    @property
    def model(self):
        """Get the User model class."""
        from app.models.user import User
        return User
