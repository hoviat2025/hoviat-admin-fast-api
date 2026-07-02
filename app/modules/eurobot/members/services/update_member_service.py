import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.models.user import User
from app.modules.eurobot.members.schemas.update_request import BotUpdateMemberRequest
from app.shared.repositories.user_base import UserBaseRepository
from app.core.exceptions import ServiceError

# Queue Models
from app.models.job_queue import JobQueue, JobStatus, JobPriority

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
            # Insert a MEDIUM priority pending job. If an active job for this user 
            # already exists, we update the priority using GREATEST
            stmt = (
                pg_insert(JobQueue)
                .values(
                    user_id=updated_user.user_id,
                    priority=JobPriority.MEDIUM.value,
                    status=JobStatus.PENDING,
                    source="eurobot"
                )
                .on_conflict_do_update(
                    index_elements=[JobQueue.user_id],
                    index_where=(JobQueue.status == JobStatus.PENDING),  # Aligned with database [1]
                    set_={  # <-- Using set_ to prevent keyword collisions [2]
                        "priority": func.greatest(JobQueue.priority, JobPriority.MEDIUM.value),
                        "updated_at": func.now()
                    }
                )
            )
            await self.db.execute(stmt)
            await self.db.commit()
            logger.info(f"Enqueued background sync task (Medium) for updated user {updated_user.user_id}")
            
        except Exception as e:
            # If the channel sync fails, we log it but do NOT crash the request.
            # The database update (Step 2 & 4) was successful, so we return the user.
            logger.error(f"User {updated_user.user_id} updated in DB, but failed to queue background sync: {e}")

        return updated_user