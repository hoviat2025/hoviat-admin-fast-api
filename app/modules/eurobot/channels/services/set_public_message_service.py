import logging
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.core.exceptions import ServiceError
from app.modules.eurobot.channels.schemas.set_public_message_request import SetPublicMessageRequest

from app.modules.eurobot.channels.repositories.stage_message_ids import TelegramMessageRepository
from app.modules.eurobot.channels.repositories.users import UserMessageUpdateRepository

logger = logging.getLogger(__name__)

class SetPublicMessageService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.stage_repo = TelegramMessageRepository(db)
        self.user_repo = UserMessageUpdateRepository(db)

    async def execute(self, payload: SetPublicMessageRequest) -> User:
        """
        Updates the staging table with public message mapping.
        If the staging row is complete, it updates the main User table.
        """
        # 1. Extract IDs and Prepare for Staging (Integers)
        lookup_msg_id_int = int(payload.original_update.message.external_reply.message_id)
        public_msg_id_int = int(payload.original_update.message.forward_origin.message_id)
        public_group_msg_id_int = int(payload.original_update.message.message_id)

        logger.info(f"Executing SetPublicMessageService for lookup_msg_id_int: {lookup_msg_id_int}")

        # 2. Upsert into Staging Table
        staging_row = await self.stage_repo.upsert_public_mapping(
            telegram_message_id=lookup_msg_id_int,
            public_message_id=public_msg_id_int,
            public_group_message_id=public_group_msg_id_int
        )

        # 3. Check for Completeness (All required columns must be populated)
        is_staging_complete = (
            staging_row.user_id is not None and
            staging_row.group_message_id is not None and
            staging_row.public_message_id is not None and
            staging_row.public_group_message_id is not None 
        )

        if not is_staging_complete:
            await self.db.commit() # Commit the staging data so it's ready for parallel services
            raise ServiceError(
                code="STAGING_INCOMPLETE",
                message=f"Staging row not complete for telegram_message_id: {lookup_msg_id_int}",
                status_code=404
            )

        # 4. Attempt Update on Main Table (One Motion)
        # Writes only to NULL columns, ensuring previously set values cannot be overwritten
        updated_user = await self.user_repo.set_message_ids_if_empty(
            user_id=staging_row.user_id,
            telegram_message_id=str(lookup_msg_id_int),
            group_message_id=str(staging_row.group_message_id),
            public_message_id=str(public_msg_id_int),
            public_group_message_id=str(public_group_msg_id_int)
        )

        # 5. Commit Transaction
        await self.db.commit()

        # 6. Return Logic
        if updated_user:
            return updated_user

        existing_user = await self.user_repo.get_by_id(staging_row.user_id)
        return existing_user