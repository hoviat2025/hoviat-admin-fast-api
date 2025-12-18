from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert
from app.models.telegram_message import TelegramMessage  # Adjust import path as needed

class TelegramMessageRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def upsert_user_mapping(self, telegram_message_id: int, user_id: int, group_message_id: int) -> TelegramMessage:
        """
        Inserts a row, or if telegram_message_id exists, ONLY updates 
        user_id and group_message_id. 
        public_message_id and public_group_message_id remain untouched.
        """
        # 1. Prepare the data to be inserted
        data = {
            "telegram_message_id": telegram_message_id,
            "user_id": user_id,
            "group_message_id": group_message_id
        }

        # 2. Create the Insert Statement
        stmt = pg_insert(TelegramMessage).values(**data)

        # 3. Handle Conflict (Update only specific fields)
        upsert_stmt = stmt.on_conflict_do_update(
            index_elements=['telegram_message_id'], # The PK to check
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
        user_id and group_message_id remain untouched.
        """
        # 1. Prepare the data to be inserted
        data = {
            "telegram_message_id": telegram_message_id,
            "public_message_id": public_message_id,
            "public_group_message_id": public_group_message_id
        }

        # 2. Create the Insert Statement
        stmt = pg_insert(TelegramMessage).values(**data)

        # 3. Handle Conflict (Update only specific fields)
        upsert_stmt = stmt.on_conflict_do_update(
            index_elements=['telegram_message_id'], # The PK to check
            set_={
                "public_message_id": stmt.excluded.public_message_id,
                "public_group_message_id": stmt.excluded.public_group_message_id
            }
        ).returning(TelegramMessage)

        result = await self.db.execute(upsert_stmt)
        return result.scalars().first()