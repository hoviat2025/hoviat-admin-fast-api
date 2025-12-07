from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.models.user import User

class UserBaseRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, user_id: int) -> User | None:
        """
        Fetches a user by their Telegram ID.
        """
        stmt = select(User).where(User.user_id == user_id)
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def update(self, user_id: int, update_data: dict) -> User | None:
        """
        Dynamic Update:
        Takes a dictionary of fields (e.g. {"score": 10, "is_ban": True})
        and updates ONLY those columns for the specific user.
        """
        # Safety check: SQLAlchemy generates invalid SQL if values() is empty
        if not update_data:
            return await self.get_by_id(user_id)

        stmt = (
            update(User)
            .where(User.user_id == user_id)
            .values(**update_data) # <--- This is the magic dynamic part
            .returning(User)
        )
        
        result = await self.db.execute(stmt)
        return result.scalars().first()