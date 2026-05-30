import logging
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.core.exceptions import ServiceError
from app.modules.eurobot.channels.schemas.set_public_message_request import SetPublicMessageRequest

# Import the specific repositories
from app.modules.eurobot.channels.repositories.stage_message_ids import TelegramMessageRepository
from app.modules.eurobot.channels.repositories.users import UserMessageUpdateRepository

logger = logging.getLogger(__name__)

class SetPublicMessageService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.stage_repo = TelegramMessageRepository(db)
        self.user_repo = UserMessageUpdateRepository(db)

    async def execute(self, payload: SetPublicMessageRequest) -> User:
        # 1. Extract IDs and Prepare for Staging (Integers)
        # The ID to search for (The Main Channel Message ID acts as the PK)
        lookup_msg_id_int = int(payload.original_update.message.external_reply.message_id)
        
        # The IDs to update (The Public Channel IDs)
        public_msg_id_int = int(payload.original_update.message.forward_origin.message_id)
        public_group_msg_id_int = int(payload.original_update.message.message_id)

        logger.info(f"Executing SetPublicMessageService for lookup_msg_id_int: {lookup_msg_id_int}")

        # 2. Upsert into Staging Table
        # This updates the 'Public' side of the equation.
        # If the row doesn't exist, it creates it. If it exists, it updates these columns.
        staging_row = await self.stage_repo.upsert_public_mapping(
            telegram_message_id=lookup_msg_id_int,
            public_message_id=public_msg_id_int,
            public_group_message_id=public_group_msg_id_int
        )
        logger.debug(f"Staging row upserted for lookup_msg_id_int: {lookup_msg_id_int}")

        # 3. Check for Completeness (Linkage)
        # We need the user_id to proceed with updating the main User table.
        # If user_id is None, it means the SetGroupMessageService hasn't run yet.
        user_id = staging_row.user_id

        if user_id is None:
            # We have successfully staged the public IDs, but we can't update the User table
            # or return a User object because the link hasn't been established yet.
            # Depending on your flow, you might want to return None or raise an error.
            # Consistent with your original logic:
            logger.warning(f"No user linked yet for telegram_message_id: {lookup_msg_id_int}. Handshake incomplete.")
            await self.db.commit() # Commit the staging data so it's ready for the other service
            raise ServiceError(
                code="USER_NOT_FOUND",
                message=f"No user linked yet for telegram_message_id: {lookup_msg_id_int}",
                status_code=404
            )

        # 4. Attempt Update on Main Table (One Motion)
        # If we have a user_id, it implies the other service ran, so `group_message_id` 
        # should be available in the staging_row.
        logger.info(f"Attempting main table update for user_id: {user_id} with public IDs.")
        updated_user = await self.user_repo.set_message_ids_if_empty(
            user_id=user_id,
            telegram_message_id=str(lookup_msg_id_int),
            group_message_id=str(staging_row.group_message_id),
            public_message_id=str(public_msg_id_int),
            public_group_message_id=str(public_group_msg_id_int)
        )

        # 5. Commit Transaction
        await self.db.commit()
        logger.debug("Database transaction committed.")

        # 6. Return Logic
        if updated_user:
            logger.info(f"Main table updated successfully for user_id: {user_id}")
            return updated_user

        # If we didn't update (because fields were already set by a parallel process),
        # or if we just staged data, we return the existing user state.
        logger.info(f"No update performed on main table. Returning existing state for user_id: {user_id}")
        existing_user = await self.user_repo.get_by_id(user_id)
        return existing_user