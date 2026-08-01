import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.models.user import User
from app.shared.repositories.job_queue import JobQueueRepository
from app.shared.repositories.user_base import UserBaseRepository
from app.core.exceptions import ServiceError
from app.modules.hilfen.members.schemas.request import HilfenInsertMemberRequest
from app.shared.user_update_policy import omit_protected_nulls

logger = logging.getLogger(__name__)

class UpsertHilfenMemberService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = UserBaseRepository(db)
        self.queue_repo = JobQueueRepository(db)

    def _clean_db_error(self, error_obj: Exception) -> str:
        """Helper to extract user-friendly messages from DB errors."""
        raw_msg = str(error_obj.orig) if hasattr(error_obj, 'orig') else str(error_obj)
        
        if "DETAIL:" in raw_msg:
            return raw_msg.split("DETAIL:", 1)[1].strip()
        
        if raw_msg.strip().startswith("<class"):
            parts = raw_msg.split(":", 1)
            if len(parts) > 1:
                return parts[1].strip()
                
        return raw_msg

    def _merge_fields(self, user_obj: User, update_data: dict) -> None:
        """
        Updates database object attributes in place after the shared bot policy has
        removed protected null assignments. Excludes primary key mutation.
        """
        for key, incoming_value in update_data.items():
            # Skip primary key modification on updates
            if key == "counter":
                continue

            if not hasattr(user_obj, key):
                continue

            setattr(user_obj, key, incoming_value)

    async def _trigger_channel_update(self, user_id: int) -> None:
        """Enqueues a medium-priority background sync task for the Hilfen bot."""
        try:
            await self.queue_repo.enqueue_medium_priority(user_id=user_id, source="hilfenbot")
            logger.info(f"Enqueued background sync task (Medium) for Hilfen user {user_id}")
        except Exception as e:
            logger.error(f"User {user_id} upserted in DB, but failed to queue background sync: {e}")

    async def execute(self, payload: HilfenInsertMemberRequest) -> User:
        """
        Executes user upsert. Attempts to find and update first. If not found, attempts insert.
        If a concurrency constraint fails, it rolls back, re-reads the database, and merges.
        After a successful commit, it triggers the Telegram channel posting pipeline.
        """
        db_data = omit_protected_nulls(payload.to_db_dict())
        user_id = db_data["user_id"]

        if user_id is None:
            raise ServiceError(
                code="INVALID_INPUT",
                message="User ID parameter is missing or invalid.",
                status_code=422
            )

        # Ensure Hilfen presence flag is set so both new inserts 
        # and existing updates cleanly flag the user as active on Hilfen.
        db_data["is_in_hilfen_bot"] = True

        # 1. Attempt Check-and-Update Route
        user = await self.repo.get_by_id(user_id)
        if user:
            self._merge_fields(user, db_data)
            await self.db.commit()
            await self.db.refresh(user)
            
            # Trigger channel post pipeline
            await self._trigger_channel_update(user_id)
            return user

        # 2. Attempt Create Route (Assumed new user)
        try:
            db_data["chat_not_found"] = False
            user = await self.repo.create(db_data)
            await self.db.commit()
            await self.db.refresh(user)
            
            # Trigger channel post pipeline
            await self._trigger_channel_update(user_id)
            return user

        except IntegrityError as e:
            # 3. Catch-and-Retry Concurrency Path
            await self.db.rollback()
            logger.warning(
                f"Atomic insert conflict hit for user_id {user_id}. "
                "Retrying with check-and-update flow after rollback."
            )

            # Re-fetch the record that was committed simultaneously by the other stream
            user = await self.repo.get_by_id(user_id)
            if user:
                self._merge_fields(user, db_data)
                await self.db.commit()
                await self.db.refresh(user)
                
                # Trigger channel post pipeline
                await self._trigger_channel_update(user_id)
                return user
            else:
                clean_message = self._clean_db_error(e)
                raise ServiceError(
                    code="CONFLICT_OCCURRED",
                    message=clean_message,
                    status_code=409
                )
        except Exception as e:
            await self.db.rollback()
            raise e
