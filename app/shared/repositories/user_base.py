from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
from app.models.user import User

class UserBaseRepository:
    """
    Contains DB logic shared by Bot, Admin, and Website.
    e.g., Finding a user by ID.
    """
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, user_id: int) -> Optional[User]:
        # Both Admin and Bot need to look up a single user
        query = select(User).where(User.user_id == user_id)
        result = await self.db.execute(query)
        return result.scalars().first()