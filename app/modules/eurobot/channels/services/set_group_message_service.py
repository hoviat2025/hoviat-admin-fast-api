from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.core.exceptions import ServiceError
from app.modules.eurobot.channels.schemas.set_group_message_request import SetGroupMessageRequest

# Import the specific repositories
from app.modules.eurobot.channels.repositories.stage_message_ids import TelegramMessageRepository
from app.modules.eurobot.channels.repositories.users import UserMessageUpdateRepository

class SetGroupMessageService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.stage_repo = TelegramMessageRepository(db)
        self.user_repo = UserMessageUpdateRepository(db)

    async def execute(self, payload: SetGroupMessageRequest) -> User:
        """
        Updates the staging table with user mapping. 
        If the staging table becomes complete (has public IDs), it updates the main User table.
        """
        user_id = payload.extracted_user_id
        
        # 1. Prepare IDs
        # Note: Staging table was defined with Integer columns, User table usually has String columns.
        telegram_msg_id_int = int(payload.original_update.message.forward_origin.message_id)
        group_msg_id_int = int(payload.original_update.message.message_id)

        # 2. Upsert into Staging Table
        # This acts as the "handshake" spot. We populate the User side of the equation.
        staging_row = await self.stage_repo.upsert_user_mapping(
            telegram_message_id=telegram_msg_id_int,
            user_id=user_id,
            group_message_id=group_msg_id_int
        )

        # 3. Check for Completeness
        # We check if the 'Public' side of the data has already arrived via a parallel process.
        is_staging_complete = (
            staging_row.public_message_id is not None and 
            staging_row.public_group_message_id is not None
        )

        updated_user = None

        if is_staging_complete:
            # 4. Attempt Update on Main Table (One Motion)
            # We only update if the main table columns are currently NULL.
            # We convert everything to str() because the main User table columns are typically VARCHAR.
            updated_user = await self.user_repo.set_message_ids_if_empty(
                user_id=user_id,
                telegram_message_id=str(telegram_msg_id_int),
                group_message_id=str(group_msg_id_int),
                public_message_id=str(staging_row.public_message_id),
                public_group_message_id=str(staging_row.public_group_message_id)
            )

        # 5. Commit everything (Staging upsert + potential User update)
        await self.db.commit()

        # 6. Return Logic
        if updated_user:
            return updated_user
        
        # If we didn't update the user (either staging incomplete or User table already filled),
        # we return the current state of the user.
        existing_user = await self.user_repo.get_by_id(user_id)
        if not existing_user:
             raise ServiceError(
                code="USER_NOT_FOUND",
                message=f"User {user_id} not found",
                status_code=404
            )
            
        return existing_user