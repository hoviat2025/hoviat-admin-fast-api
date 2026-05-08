import logging
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.modules.eurobot.members.schemas.update_request import BotUpdateMemberRequest
from app.shared.repositories.user_base import UserBaseRepository
from app.core.exceptions import ServiceError

# --- ADDED IMPORTS ---
from app.modules.eurobot.channels.services.update_channel_post_service import UpdateChannelPostService
from app.modules.eurobot.channels.schemas.update_post_request import UpdateChannelPostRequest

logger = logging.getLogger(__name__)

class UpdateMemberService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = UserBaseRepository(db)

    async def execute(self, payload: BotUpdateMemberRequest) -> User:
        # 1. Business Logic: Prepare Data
        update_data = payload.model_dump(exclude_unset=True, exclude={"user_id"})

        if not update_data:
            raise ServiceError(code="INVALID_INPUT", message="No fields provided for update", status_code=422)

        # 2. Data Access: Call the Repo
        updated_user = await self.repo.update(
            user_id=payload.user_id, 
            update_data=update_data
        )

        # 3. Business Logic: Check Existence
        if not updated_user:
            raise ServiceError(
                code="USERID_NOT_FOUND", 
                message=f"No user exists with user_id {payload.user_id}",
                status_code=404
            )
        
        # 4. Transaction Management: Commit
        # We commit here so the DB has the latest data before the channel service runs.
        await self.db.commit()
        
        # 5. Call Update Channel Service
        try:
            # We initialize the service
            update_service = UpdateChannelPostService(self.db)
            
            # We prepare the request using the user_id from the payload (or the object)
            update_payload = UpdateChannelPostRequest(user_id=updated_user.user_id)
            
            # Execute the update. 
            # We assign the result back to `updated_user` because the service 
            # might have updated the `channel_updated_at` or message ID fields.
            updated_user = await update_service.execute(updated_user.user_id)
            
        except Exception as e:
            # If the channel sync fails, we log it but do NOT crash the request.
            # The database update (Step 2 & 4) was successful, so we return the user.
            logger.error(f"User {updated_user.user_id} updated in DB, but failed to sync channel post: {e}")

        return updated_user