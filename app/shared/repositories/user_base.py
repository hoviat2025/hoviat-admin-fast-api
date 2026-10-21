from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import case, func, select, update, insert
from sqlalchemy.dialects.postgresql import insert as pg_insert 
from app.models.user import User

class UserBaseRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, user_id: int) -> User | None:
        stmt = select(User).where(User.user_id == user_id)
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def get_by_id_for_update(self, user_id: int) -> User | None:
        """Fetch and lock one user until the current transaction completes."""
        stmt = (
            select(User)
            .where(User.user_id == user_id)
            .with_for_update()
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def get_fresh_by_id(self, user_id: int, session: AsyncSession | None = None) -> User | None:
        """
        Fetches the user directly from the database, bypassing and overwriting 
        the session identity map cache. Use this for polling external state changes.
        """
        s = session or self.db
        stmt = (
            select(User)
            .where(User.user_id == user_id)
            .execution_options(populate_existing=True)
        )
        result = await s.execute(stmt)
        return result.scalars().first()

    async def get_by_telegram_message_id(self, message_id: str) -> User | None:
        stmt = select(User).where(User.telegram_message_id == message_id)
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def get_by_public_message_id(self, message_id: str) -> User | None:
        stmt = select(User).where(User.public_message_id == message_id)
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def get_by_hilfen_message_id(self, message_id: int) -> User | None:
        stmt = select(User).where(User.hilfen_message_id == message_id)
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

    @staticmethod
    def _preserve_public_name(values: dict) -> dict:
        """Bot identities seed blank names; explicit account/admin edits own them.

        Use SQL CASE rather than read/check/write so a concurrent profile edit
        cannot be replaced by a stale Telegram identity update.
        """
        values = dict(values)
        if "nickname" in values:
            incoming = (values["nickname"] or "").strip()
            if not incoming:
                values.pop("nickname")
            else:
                values["nickname"] = case(
                    (func.nullif(func.regexp_replace(User.nickname, r"\s+", "", "g"), "").is_(None), incoming),
                    else_=User.nickname,
                )
        return values

    async def upsert(self, data: dict, *, preserve_existing_nickname: bool = False) -> User:
        """
        Inserts a user, or updates if user_id already exists.
        """
        if preserve_existing_nickname and "nickname" in data:
            data = dict(data)
            cleaned_name = (data["nickname"] or "").strip()
            if cleaned_name:
                data["nickname"] = cleaned_name
            else:
                data.pop("nickname")
        # 1. Prepare Statement
        stmt = pg_insert(User).values(**data)
        
        # 2. Define Update Logic (Update everything except user_id itself)
        # We assume 'user_id' is the conflict target.
        update_dict = {k: v for k, v in data.items() if k != 'user_id'}
        if preserve_existing_nickname:
            update_dict = self._preserve_public_name(update_dict)
        
        # 3. Handle Conflict
        if not update_dict:
            result = await self.db.execute(stmt.on_conflict_do_nothing(index_elements=["user_id"]).returning(User))
            return result.scalars().first() or await self.get_by_id(data["user_id"])
        upsert_stmt = stmt.on_conflict_do_update(
            index_elements=['user_id'], # The unique constraint to check
            set_=update_dict            # The columns to update if conflict occurs
        ).returning(User)
        
        result = await self.db.execute(upsert_stmt)
        return result.scalars().first()

    async def update(self, user_id: int, update_data: dict, *, preserve_existing_nickname: bool = False) -> User | None:
        if preserve_existing_nickname:
            update_data = self._preserve_public_name(update_data)
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
