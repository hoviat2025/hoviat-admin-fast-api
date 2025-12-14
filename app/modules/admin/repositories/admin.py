from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.admin import Admin

class AdminRepository:
    """
    Handles direct database operations for the 'admins' table.
    """
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_username(self, username: str) -> Optional[Admin]:
        """
        Used primarily during Login to find credentials.
        """
        query = select(Admin).where(Admin.username == username)
        result = await self.db.execute(query)
        return result.scalars().first()

    async def get_by_id(self, admin_id: int) -> Optional[Admin]:
        """
        Used by the dependency system to validate the JWT against the DB.
        """
        return await self.db.get(Admin, admin_id)