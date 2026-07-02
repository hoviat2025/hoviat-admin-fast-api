import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert

# Core & Models
from app.models.user import User
from app.shared.repositories.user_base import UserBaseRepository
from app.core.exceptions import ServiceError

# Schemas
from app.modules.eurobot.members.schemas.insert_request import BotInsertMemberRequest

# Queue Models
from app.models.job_queue import JobQueue, JobStatus, JobPriority

logger = logging.getLogger(__name__)

class InsertMemberService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = UserBaseRepository(db)

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

    async def execute(self, payload: BotInsertMemberRequest) -> User:
        # 1. Prepare Data
        insert_data = payload.model_dump(exclude_unset=True)
        
        # Business Rule: Explicitly set chat_not_found to False & set Eurobot presence
        insert_data["chat_not_found"] = False
        insert_data["is_in_eurobot"] = True

        try:
            # 2. Call Repo (Creates the user object in session)
            new_user = await self.repo.create(insert_data)
            
            # 3. Commit Transaction
            # This saves the user to the DB first.
            await self.db.commit()
            
            # Refresh ensures the instance is up-to-date and attached to the session
            await self.db.refresh(new_user)

            # 4. Queue Background Channel Sync (Medium Priority)
            try:
                # Insert a MEDIUM priority pending job. If an active job for this user 
                # already exists, we update the priority using GREATEST
                stmt = (
                    pg_insert(JobQueue)
                    .values(
                        user_id=new_user.user_id,
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
                logger.info(f"Enqueued background sync task (Medium) for newly inserted user {new_user.user_id}")
                
            except Exception as e:
                # If the channel update fails, we log it but do NOT rollback the User creation.
                # The user was successfully created in step 3.
                logger.error(f"User {new_user.user_id} created, but failed to queue background sync: {e}")
                
            return new_user

        except IntegrityError as e:
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