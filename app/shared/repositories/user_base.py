from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, insert
from sqlalchemy.dialects.postgresql import insert as pg_insert 
from app.models.user import User

class UserBaseRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, user_id: int) -> User | None:
        stmt = select(User).where(User.user_id == user_id)
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def get_fresh_by_id(self, user_id: int) -> User | None:
        """
        Fetches the user directly from the database, bypassing and overwriting 
        the session identity map cache. Use this for polling external state changes.
        """
        stmt = (
            select(User)
            .where(User.user_id == user_id)
            .execution_options(populate_existing=True)
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def get_by_telegram_message_id(self, message_id: str) -> User | None:
        stmt = select(User).where(User.telegram_message_id == message_id)
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def get_by_public_message_id(self, message_id: str) -> User | None:
        stmt = select(User).where(User.public_message_id == message_id)
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def create(self, create_data: dict) -> User:
        stmt = (
            insert(User)
            .values(**create_data)
            .returning(User)
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def upsert(self, data: dict) -> User:
        """
        Inserts a user, or updates if user_id already exists.
        """
        # 1. Prepare Statement
        stmt = pg_insert(User).values(**data)
        
        # 2. Define Update Logic (Update everything except user_id itself)
        # We assume 'user_id' is the conflict target.
        update_dict = {k: v for k, v in data.items() if k != 'user_id'}
        
        # 3. Handle Conflict
        upsert_stmt = stmt.on_conflict_do_update(
            index_elements=['user_id'], # The unique constraint to check
            set_=update_dict            # The columns to update if conflict occurs
        ).returning(User)
        
        result = await self.db.execute(upsert_stmt)
        return result.scalars().first()

    async def update(self, user_id: int, update_data: dict) -> User | None:
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