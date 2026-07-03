import logging
import asyncio
from datetime import datetime
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.encoders import jsonable_encoder

# Core & Config
from app.core.config import settings
from app.core.exceptions import ServiceError
from app.shared.repositories.user_base import UserBaseRepository
from app.shared.repositories.job_queue import JobQueueRepository
from app.models.job_queue import JobStatus

# Local Message Formatter (reuse eurobot formatter)
from app.modules.eurobot.channels.services.format_messages import create_telegram_message

logger = logging.getLogger(__name__)


class GetHilfenQuoteReplyInfoService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = UserBaseRepository(db)
        self.queue_repo = JobQueueRepository(db)

    async def execute(self, user_id: int) -> Dict[str, Any]:
        logger.info(f"Executing GetHilfenQuoteReplyInfoService for user_id: {user_id}")

        user = await self.repo.get_by_id(user_id)
        if not user:
            logger.warning(f"User {user_id} not found in database.")
            raise ServiceError(
                code="USER_NOT_FOUND",
                message=f"User {user_id} not found",
                status_code=404,
            )

        # Determine whether we need to sync to channel
        should_update = False
        if not user.telegram_message_id:
            should_update = True
        elif not user.hilfen_message_id:
            should_update = True
        elif user.channel_updated_at is None:
            should_update = True
        elif user.updated_at and user.updated_at >= user.channel_updated_at:
            should_update = True

        logger.info(f"User {user_id} should_update evaluated to: {should_update}")

        if should_update:
            try:
                logger.info(f"Enqueuing HIGH-priority job for hilfen user {user_id}")
                await self.queue_repo.enqueue_high_priority(user_id=user_id, source="hilfenbot")

                # Poll and await completion
                start_time = datetime.now()
                timeout_seconds = 45

                while (datetime.now() - start_time).total_seconds() < timeout_seconds:
                    async with AsyncSession(self.db.bind) as read_session:
                        active_job = await self.queue_repo.get_active_job(user_id, session=read_session)

                    if not active_job:
                        async with AsyncSession(self.db.bind) as read_session:
                            final_job = await self.queue_repo.get_latest_job(user_id, session=read_session)
                        if final_job and final_job.status == JobStatus.COMPLETED:
                            logger.info(f"VIP sync completed successfully for user {user_id}")
                            break
                        if final_job and final_job.status == JobStatus.FAILED:
                            raise Exception(f"Queue task failed: {final_job.error_message}")
                        break

                    await asyncio.sleep(1.0)
                else:
                    raise asyncio.TimeoutError("Timeout exceeded waiting for queue worker.")

                async with AsyncSession(self.db.bind) as read_session:
                    user = await self.repo.get_fresh_by_id(user_id, session=read_session)
                if not user:
                    raise ServiceError(
                        code="USER_NOT_FOUND",
                        message=f"User {user_id} not found",
                        status_code=404,
                    )

            except Exception as e:
                logger.error(f"Failed to synchronize channel post for user {user_id} via queue: {e}")
                raise ServiceError(
                    code="CHANNEL_SYNC_FAILED",
                    message="Failed to synchronize user data with Telegram Channel",
                    status_code=500,
                )

        # Generate components
        logger.debug(f"Generating formatter components locally for user {user_id}")
        components = self._generate_formatter_components(user)
        if not isinstance(components, dict):
            components = {}

        response_data = components.copy()
        response_data.update(
            {
                "channel_message_id": user.telegram_message_id,
                "channel_id": getattr(settings, "MAIN_CHANNEL_ID", None),

                "group_message_id": user.group_message_id,
                "group_id": getattr(settings, "MAIN_GROUP_ID", None),

                "public_group_message_id": user.public_group_message_id,
                "public_group_id": getattr(settings, "PUBLIC_GROUP_ID", None),

                "public_message_id": user.public_message_id,
                "public_channel_id": getattr(settings, "PUBLIC_CHANNEL_ID", None),

                "hilfen_message_id": user.hilfen_message_id,
                "hilfen_group_message_id": user.hilfen_group_message_id,
                "hilfen_channel_id": getattr(settings, "HILFEN_CHANNEL_ID", None),
                "hilfen_group_id": getattr(settings, "HILFEN_GROUP_ID", None),
            }
        )

        logger.info(f"GetHilfenQuoteReplyInfoService completed successfully for user_id: {user_id}")
        return response_data

    def _generate_formatter_components(self, user) -> Dict[str, Any]:
        try:
            user_data = jsonable_encoder(user, exclude={"password", "token"})
            result = create_telegram_message(user_data)
            return result.get("components", {})
        except Exception as e:
            logger.error(f"Error formatting message components locally for user {getattr(user, 'user_id', 'unknown')}: {e}")
            raise ServiceError(
                code="FORMATTER_ERROR",
                message="Local formatter execution failed",
                status_code=500,
            )
