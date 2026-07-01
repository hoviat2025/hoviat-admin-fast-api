import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.models.user import User
from app.modules.eurobot.members.schemas.insert_request import BotInsertMemberRequest
from app.shared.repositories.user_base import UserBaseRepository
from app.core.exceptions import ServiceError

# Queue Models
from app.models.job_queue import JobQueue, JobStatus, JobPriority

logger = logging.getLogger(__name__)

class UpsertMemberService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = UserBaseRepository(db)

    def _clean_db_error(self, error_obj: Exception) -> str:
        """Extract user-friendly message from DB error."""
        raw_msg = str(error_obj.orig) if hasattr(error_obj, 'orig') else str(error_obj)
        if "DETAIL:" in raw_msg:
            return raw_msg.split("DETAIL:", 1)[1].strip()
        if raw_msg.strip().startswith("<class"):
            parts = raw_msg.split(":", 1)
            if len(parts) > 1:
                return parts[1].strip()
        return raw_msg

    async def execute(self, payload: BotInsertMemberRequest) -> User:
        # 1. Prepare Data
        upsert_data = payload.model_dump(exclude_unset=True)
        
        # Business Rule: Reset chat_not_found
        upsert_data["chat_not_found"] = False

        try:
            # 2. Call Repo (Upsert)
            user = await self.repo.upsert(upsert_data)
            
            # 3. Commit
            # Save the upsert changes to the DB first.
            await self.db.commit()

            # Refreshing ensures the object is bound to the session and up-to-date
            # before passing it to the next service.
            await self.db.refresh(user)

            # 4. Queue Background Channel Sync (Medium Priority)
            try:
                # Insert a MEDIUM priority pending job. If an active job for this user 
                # already exists, we update the priority using GREATEST
                stmt = (
                    pg_insert(JobQueue)
                    .values(
                        user_id=user.user_id,
                        priority=JobPriority.MEDIUM.value,
                        status=JobStatus.PENDING,
                        source="eurobot"
                    )
                    .on_conflict_do_update(
                        index_elements=[JobQueue.user_id],
                        index_where=(JobQueue.status == JobStatus.PENDING),  # Aligned with database
                        set_={
                            "priority": func.greatest(JobQueue.priority, JobPriority.MEDIUM.value),
                            "updated_at": func.now()
                        }
                    )
                )
                await self.db.execute(stmt)
                await self.db.commit()
                logger.info(f"Enqueued background sync task (Medium) for user {user.user_id}")

            except Exception as e:
                # Log the error but do NOT rollback or crash the Upsert.
                # The user data is already committed and safe in the DB.
                logger.error(f"User {user.user_id} upserted, but failed to queue background sync: {e}")

            return user

        except IntegrityError as e:
            # This catches conflicts on columns OTHER than user_id (e.g. counter)
            await self.db.rollback()
            clean_message = self._clean_db_error(e)
            
            raise ServiceError(
                code="CONFLICT_OCCURRED",
                message=clean_message,
                status_code=409
            )
        except Exception as e:
            await self.db.rollback()
            raise e