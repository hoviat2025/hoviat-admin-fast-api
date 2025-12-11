import logging
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

# Models
from app.models.user import User

# The Logic We Are Reusing
from app.modules.eurobot.channels.services.update_channel_post_service import UpdateChannelPostService
from app.modules.eurobot.channels.schemas.update_post_request import UpdateChannelPostRequest

logger = logging.getLogger(__name__)

class BatchUpdateChannelService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def execute(self, limit: int = 25) -> Dict[str, Any]:
        """
        Fetches users with no telegram_message_id and tries to sync them.
        Returns a summary report.
        """
        # 1. Fetch Candidates (IDs ONLY)
        # CRITICAL FIX: We select(User.user_id) instead of select(User).
        # This prevents "greenlet_spawn" errors caused by holding object references
        # while the session is being committed/expired inside the loop.
        stmt = select(User.user_id).where(User.telegram_message_id.is_(None)).limit(limit)
        
        result = await self.db.execute(stmt)
        candidate_ids = result.scalars().all() # This is now a list of Integers [1, 2, 3...]

        report = {
            "total_candidates": len(candidate_ids),
            "processed": 0,
            "success": 0,
            "failed": 0,
            "failed_ids": []
        }

        if not candidate_ids:
            return report

        logger.info(f"Batch Sync: Found {len(candidate_ids)} users to process.")

        # 2. Iterate and Process (Sequential Queue)
        # Because we use 'await' inside the loop, this will strictly process
        # User 1, wait for finish, then User 2, wait for finish, etc.
        for user_id in candidate_ids:
            try:
                # Reuse the existing logic
                # We instantiate per user to keep logic clean, though DB session is shared
                update_service = UpdateChannelPostService(self.db)
                payload = UpdateChannelPostRequest(user_id=user_id)
                
                # This 'await' ensures we don't move to the next user until this one is done
                await update_service.execute(payload)
                
                report["success"] += 1
                logger.info(f"Batch Sync: User {user_id} success.")
                
            except Exception as e:
                report["failed"] += 1
                report["failed_ids"].append(user_id)
                logger.error(f"Batch Sync: Failed for User {user_id}. Error: {str(e)}")
                
                # Cleanup connection for the next user in the queue
                try:
                    await self.db.rollback()
                except Exception as rollback_err:
                    logger.critical(f"Batch Sync: DB Rollback failed for {user_id}: {rollback_err}")

            report["processed"] += 1

        return report