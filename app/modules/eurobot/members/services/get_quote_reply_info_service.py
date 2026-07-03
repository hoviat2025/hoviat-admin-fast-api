import logging
import asyncio
from datetime import datetime
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from fastapi.encoders import jsonable_encoder

# Core & Config
from app.core.config import settings
from app.core.exceptions import ServiceError
from app.shared.repositories.user_base import UserBaseRepository

# Queue Models
from app.models.job_queue import JobQueue, JobStatus, JobPriority

# Local Message Formatter
from app.modules.eurobot.channels.services.format_messages import create_telegram_message

logger = logging.getLogger(__name__)

class GetQuoteReplyInfoService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = UserBaseRepository(db)

    async def execute(self, user_id: int) -> Dict[str, Any]:
        """
        1. Syncs User with Channel via DB queue if needed.
        2. Generates 'components' using local formatter service.
        3. Returns a flattened dictionary containing components + ID fields.
        """
        logger.info(f"Executing GetQuoteReplyInfoService for user_id: {user_id}")
        
        # 1. Get User
        user = await self.repo.get_by_id(user_id)
        if not user:
            logger.warning(f"User {user_id} not found in database.")
            raise ServiceError(
                code="USER_NOT_FOUND",
                message=f"User {user_id} not found",
                status_code=404
            )

        # 2. Check Conditions for Update
        should_update = False
        
        if not user.telegram_message_id:
            should_update = True
        elif not user.public_message_id:
            should_update = True
        elif user.channel_updated_at is None:
            should_update = True
        elif user.updated_at and user.updated_at >= user.channel_updated_at:
            should_update = True

        logger.info(f"User {user_id} should_update evaluated to: {should_update}")

        # 3. Queue and Await VIP Sync if needed
        if should_update:
            try:
                logger.info(f"Enqueuing VIP update task for user {user_id}")
                
                # Insert a HIGH priority pending job. If an active job for this user 
                # already exists, upgrade its priority to HIGH
                stmt = (
                    pg_insert(JobQueue)
                    .values(
                        user_id=user_id,
                        priority=JobPriority.HIGH.value,
                        status=JobStatus.PENDING,
                        source="eurobot"
                    )
                    .on_conflict_do_update(
                        index_elements=[JobQueue.user_id],
                        index_where=(JobQueue.status == JobStatus.PENDING),  # Aligned with database
                        set_={
                            "priority": func.greatest(JobQueue.priority, JobPriority.HIGH.value),
                            "updated_at": func.now()
                        }
                    )
                )
                await self.db.execute(stmt)
                await self.db.commit()

                # Poll and await the task's completion (VIP request-response style)
                start_time = datetime.now()
                timeout_seconds = 45
                
                while (datetime.now() - start_time).total_seconds() < timeout_seconds:
                    await self.db.commit()
                    
                    # Check if the job is still active
                    stmt_poll = (
                        select(JobQueue)
                        .where(JobQueue.user_id == user_id)
                        .where(JobQueue.status.in_([JobStatus.PENDING, JobStatus.PROCESSING]))
                        .execution_options(populate_existing=True)
                    )
                    active_job = (await self.db.execute(stmt_poll)).scalars().first()
                    
                    if not active_job:
                        # Fetch the final completed state
                        stmt_final = (
                            select(JobQueue)
                            .where(JobQueue.user_id == user_id)
                            .order_by(JobQueue.id.desc())
                            .limit(1)
                            .execution_options(populate_existing=True)
                        )
                        final_job = (await self.db.execute(stmt_final)).scalars().first()
                        
                        if final_job and final_job.status == JobStatus.COMPLETED:
                            logger.info(f"VIP sync completed successfully for user {user_id}")
                            break
                        elif final_job and final_job.status == JobStatus.FAILED:
                            raise Exception(f"Queue task failed: {final_job.error_message}")
                        else:
                            break
                    
                    await asyncio.sleep(0.5)
                else:
                    raise asyncio.TimeoutError("Timeout exceeded waiting for queue worker.")

                user = await self.repo.get_fresh_by_id(user_id)
                if not user:
                    raise ServiceError(
                        code="USER_NOT_FOUND",
                        message=f"User {user_id} not found",
                        status_code=404
                    )

            except Exception as e:
                logger.error(f"Failed to synchronize channel post for user {user_id} via queue: {e}")
                raise ServiceError(
                    code="CHANNEL_SYNC_FAILED", 
                    message="Failed to synchronize user data with Telegram Channel", 
                    status_code=500
                )

        # 4. Generate Formatter Components
        logger.debug(f"Generating formatter components locally for user {user_id}")
        components = self._generate_formatter_components(user)
        if not isinstance(components, dict):
            components = {}

        # 5. Construct Final Flattened Data
        response_data = components.copy()
        
        response_data.update({
            "channel_message_id": user.telegram_message_id,
            "channel_id": getattr(settings, "MAIN_CHANNEL_ID", None),
            
            "group_message_id": user.group_message_id,
            "group_id": getattr(settings, "MAIN_GROUP_ID", None),
            
            "public_group_message_id": user.public_group_message_id,
            "public_group_id": getattr(settings, "PUBLIC_GROUP_ID", None),
            
            "public_message_id": user.public_message_id,
            "public_channel_id": getattr(settings, "PUBLIC_CHANNEL_ID", None)
        })

        logger.info(f"GetQuoteReplyInfoService completed successfully for user_id: {user_id}")
        return response_data

    def _generate_formatter_components(self, user) -> Dict[str, Any]:
        """Converts user model to dict and processes it via the local formatting function."""
        try:
            user_data = jsonable_encoder(user, exclude={"password", "token"})
            result = create_telegram_message(user_data)
            return result.get("components", {})
            
        except Exception as e:
            logger.error(f"Error formatting message components locally for user {user.user_id}: {e}")
            raise ServiceError(
                code="FORMATTER_ERROR", 
                message="Local formatter execution failed", 
                status_code=500
            )