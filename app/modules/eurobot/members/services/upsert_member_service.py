import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.models.user import User
from app.modules.eurobot.members.schemas.insert_request import BotInsertMemberRequest
from app.shared.repositories.user_base import UserBaseRepository
from app.shared.repositories.job_queue import JobQueueRepository
from app.core.exceptions import ServiceError
from app.shared.user_update_policy import omit_protected_nulls

logger = logging.getLogger(__name__)

class UpsertMemberService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = UserBaseRepository(db)
        self.queue_repo = JobQueueRepository(db)

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
        upsert_data = omit_protected_nulls(payload.model_dump(exclude_unset=True))
        
        # Channel synchronization is the sole owner of chat_not_found. An
        # ordinary bot upsert must preserve the last getChat result.
        upsert_data["is_in_eurobot"] = True

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
                await self.queue_repo.enqueue_medium_priority(user_id=user.user_id, source="eurobot")
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
