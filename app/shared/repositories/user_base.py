from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.models.user import User

class UserBaseRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, user_id: int) -> User | None:
        """
        Fetches a user by their Telegram User ID.
        """
        stmt = select(User).where(User.user_id == user_id)
        result = await self.db.execute(stmt)
        return result.scalars().first()

    # --- NEW METHOD ---
    async def get_by_telegram_message_id(self, message_id: str) -> User | None:
        """
        Fetches a user by the message_id of their post in the Main Channel.
        Used for mapping replies/forwards back to the user.
        """
        stmt = select(User).where(User.telegram_message_id == message_id)
        result = await self.db.execute(stmt)
        return result.scalars().first()
    # ------------------

    async def update(self, user_id: int, update_data: dict) -> User | None:
        """
        Dynamic Update by User ID.
        """
        if not update_data:
            return await self.get_by_id(user_id)

        stmt = (
            update(User)
            .where(User.user_id == user_id)
            .values(**update_data)
            .returning(User)
        )
        
        result = await self.db.execute(stmt)
        return result.scalars().first()