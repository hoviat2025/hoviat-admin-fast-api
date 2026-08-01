import logging
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.modules.eurobot.members.schemas.update_request import BotUpdateMemberRequest
from app.shared.repositories.job_queue import JobQueueRepository
from app.shared.repositories.user_base import UserBaseRepository
from app.core.exceptions import ServiceError
from app.shared.user_update_policy import omit_protected_nulls

logger = logging.getLogger(__name__)

class UpdateMemberService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = UserBaseRepository(db)
        self.queue_repo = JobQueueRepository(db)

    async def execute(self, payload: BotUpdateMemberRequest) -> User:
        # 1. Business Logic: Prepare Data
        update_data = omit_protected_nulls(
            payload.model_dump(exclude_unset=True, exclude={"user_id"})
        )

        # Set Eurobot presence flag upon active profile update
        update_data["is_in_eurobot"] = True

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
        
        # 5. Queue Background Channel Sync (Medium Priority)
        try:
            await self.queue_repo.enqueue_medium_priority(user_id=updated_user.user_id, source="eurobot")
            logger.info(f"Enqueued background sync task (Medium) for updated user {updated_user.user_id}")
            
        except Exception as e:
            # If the channel sync fails, we log it but do NOT crash the request.
            # The database update (Step 2 & 4) was successful, so we return the user.
            logger.error(f"User {updated_user.user_id} updated in DB, but failed to queue background sync: {e}")

        return updated_user
