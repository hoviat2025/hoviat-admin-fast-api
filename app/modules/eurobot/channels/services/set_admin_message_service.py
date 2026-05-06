from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.core.exceptions import ServiceError
from app.modules.eurobot.channels.schemas.set_admin_message_request import SetAdminMessageRequest

# Import the specific repositories
from app.modules.eurobot.channels.repositories.stage_message_ids import TelegramMessageRepository
from app.modules.hilfen.repositories.user_repository import HilfenUserRepository

class SetAdminMessageService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.stage_repo = TelegramMessageRepository(db)
        self.user_repo = HilfenUserRepository(db)

    async def execute(self, payload: SetAdminMessageRequest) -> User:
        """
        Updates the staging table with admin message mapping. 
        If the staging table becomes complete (has all 6 IDs), it updates the main User table.
        """
        # 1. Extract IDs and Prepare for Staging (Integers)
        # The ID to search for (The Main Channel Message ID acts as the PK)
        lookup_msg_id_int = int(payload.original_update.message.external_reply.message_id)
        
        # The IDs to update (The admin Channel IDs)
        admin_msg_id_int = int(payload.original_update.message.forward_origin.message_id)
        admin_group_msg_id_int = int(payload.original_update.message.message_id)

        # 2. Upsert into Staging Table
        # This updates the 'admin' side of the equation.
        # If the row doesn't exist, it creates it. If it exists, it updates these columns.
        staging_row = await self.stage_repo.upsert_admin_mapping(
            telegram_message_id=lookup_msg_id_int,
            admin_message_id=admin_msg_id_int,
            admin_group_message_id=admin_group_msg_id_int
        )

        # 3. Check for Completeness (4 columns must be populated)
        # We need to check all columns to determine if staging is complete
        is_staging_complete = (
            staging_row.user_id is not None and
            staging_row.group_message_id is not None and
            staging_row.admin_message_id is not None and
            staging_row.admin_group_message_id is not None
        )

        if not is_staging_complete:
            # We have successfully staged the admin IDs, but we can't update the User table
            # or return a User object because the staging row isn't complete yet.
            await self.db.commit() # Commit the staging data so it's ready for the other services
            raise ServiceError(
                code="STAGING_INCOMPLETE",
                message=f"Staging row not complete for telegram_message_id: {lookup_msg_id_int}",
                status_code=404
            )

        # 4. Attempt Update on Main Table (One Motion)
        # All staging data is available, so we can update the user table
        updated_user = await self.user_repo.set_admin_message_ids_if_empty(
            user_id=staging_row.user_id,
            telegram_message_id=str(lookup_msg_id_int),
            group_message_id=str(staging_row.group_message_id),
            admin_message_id=str(staging_row.admin_message_id),
            admin_group_message_id=str(staging_row.admin_group_message_id)
        )

        # 5. Commit Transaction
        await self.db.commit()

        # 6. Return Logic
        if updated_user:
            return updated_user

        # If we didn't update (because fields were already set by a parallel process),
        # we return the existing user state.
        existing_user = await self.user_repo.get_by_id(staging_row.user_id)
        return existing_user
