from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert
from app.models.telegram_message import TelegramMessage

class TelegramMessageRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def upsert_user_mapping(self, telegram_message_id: int, user_id: int, group_message_id: int) -> TelegramMessage:
        """
        Inserts a row, or if telegram_message_id exists, ONLY updates 
        user_id and group_message_id.
        """
        data = {
            "telegram_message_id": telegram_message_id,
            "user_id": user_id,
            "group_message_id": group_message_id
        }

        stmt = pg_insert(TelegramMessage).values(**data)

        upsert_stmt = stmt.on_conflict_do_update(
            index_elements=['telegram_message_id'],
            set_={
                "user_id": stmt.excluded.user_id,
                "group_message_id": stmt.excluded.group_message_id
            }
        ).returning(TelegramMessage)

        result = await self.db.execute(upsert_stmt)
        return result.scalars().first()

    async def upsert_public_mapping(self, telegram_message_id: int, public_message_id: int, public_group_message_id: int) -> TelegramMessage:
        """
        Inserts a row, or if telegram_message_id exists, ONLY updates 
        public_message_id and public_group_message_id.
        """
        data = {
            "telegram_message_id": telegram_message_id,
            "public_message_id": public_message_id,
            "public_group_message_id": public_group_message_id
        }

        stmt = pg_insert(TelegramMessage).values(**data)

        upsert_stmt = stmt.on_conflict_do_update(
            index_elements=['telegram_message_id'],
            set_={
                "public_message_id": stmt.excluded.public_message_id,
                "public_group_message_id": stmt.excluded.public_group_message_id
            }
        ).returning(TelegramMessage)

        result = await self.db.execute(upsert_stmt)
        return result.scalars().first()

    async def upsert_hilfen_mapping(self, telegram_message_id: int, hilfen_message_id: int, hilfen_group_message_id: int) -> TelegramMessage:
        """
        Inserts a row, or if telegram_message_id exists, ONLY updates 
        hilfen_message_id and hilfen_group_message_id.
        """
        data = {
            "telegram_message_id": telegram_message_id,
            "hilfen_message_id": hilfen_message_id,
            "hilfen_group_message_id": hilfen_group_message_id
        }

        stmt = pg_insert(TelegramMessage).values(**data)

        upsert_stmt = stmt.on_conflict_do_update(
            index_elements=['telegram_message_id'],
            set_={
                "hilfen_message_id": stmt.excluded.hilfen_message_id,
                "hilfen_group_message_id": stmt.excluded.hilfen_group_message_id
            }
        ).returning(TelegramMessage)

        result = await self.db.execute(upsert_stmt)
        return result.scalars().first()