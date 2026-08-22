from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_privacy_settings import UserPrivacySettings


class PrivacyRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self, user_id: int) -> UserPrivacySettings | None:
        return await self.db.scalar(
            select(UserPrivacySettings).where(UserPrivacySettings.user_id == user_id)
        )

    async def upsert(self, user_id: int, data: dict) -> None:
        """
        Insert-or-update the privacy row for a user.
        """
        values = dict(data)
        values["user_id"] = user_id

        stmt = pg_insert(UserPrivacySettings).values(**values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["user_id"],
            set_={k: v for k, v in values.items() if k != "user_id"},
        )
        await self.db.execute(stmt)
