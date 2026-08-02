import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_

# Database Models
from app.models.user import User
from app.models.job_queue import JobQueue, JobStatus

# Repositories
from app.shared.repositories.job_queue import JobQueueRepository

logger = logging.getLogger(__name__)

class CronSyncService:
    def __init__(self, db: AsyncSession):
        self.db = db
        # Instantiate the Repository wrapper
        self.queue_repo = JobQueueRepository(db)

    async def execute(self, batch_size: int = 20) -> dict:
        """
        Scans the database for users missing their respective Telegram channel posts
        or whose channel posts are out of sync with their latest database profile state,
        and enqueues them at LOW priority.
        
        Guarantees that we never fetch or enqueue users who already have active 
        or pending jobs in the queue.
        """
        logger.info(f"⏳ Running Universal CronSyncService (Batch Size: {batch_size})")

        # 1. Query for users needing sync who are NOT already in the queue
        # We perform a subquery exists check to exclude active tasks
        # (This is a cleaner approach to avoid multiple queue entries per user)
        active_jobs_subq = (
            select(JobQueue.id)
            .where(
                JobQueue.user_id == User.user_id,
                JobQueue.status.in_([JobStatus.PENDING, JobStatus.PROCESSING])
            )
            .exists()
        )

        # Build the sync filter to catch both completely missing and out-of-sync posts
        sync_needed_filter = or_(
            # Case A: Missing the main channel post entirely
            User.telegram_message_id.is_(None),
            
            # Case B: Present in Eurobot but missing the Eurobot public post
            and_(User.is_in_eurobot == True, User.public_message_id.is_(None)),
            
            # Case C: Present in Hilfenbot but missing the Hilfen channel post
            and_(User.is_in_hilfen_bot == True, User.hilfen_message_id.is_(None)),
            
            # Case D: Out of Sync (The post exists, but user profile was updated after the last channel sync)
            and_(
                User.telegram_message_id.is_not(None),
                or_(
                    User.channel_updated_at.is_(None),
                    User.updated_at > User.channel_updated_at
                )
            )
        )

        stmt = (
            select(User)
            .where(
                ~active_jobs_subq,            # Queue Avoidance Shield: Must not be in queue
                sync_needed_filter            # Target missing or out-of-sync posts
            )
            # Low-priority enqueue holds per-user transaction locks until the
            # batch commit, so every concurrent batch must acquire them in the
            # same deterministic order.
            .order_by(User.user_id.asc())
            .limit(batch_size)
        )
        
        result = await self.db.execute(stmt)
        users_to_sync = result.scalars().all()
        
        if not users_to_sync:
            logger.info("✅ All users are fully synced. No cron tasks enqueued.")
            return {"status": "success", "enqueued_count": 0}

        enqueued_count = 0

        # 2. Loop through candidates and enqueue them
        for user in users_to_sync:
            try:
                # Resolve source directly based on their active platform presence flags
                if user.is_in_eurobot and user.is_in_hilfen_bot:
                    source = "both"
                elif user.is_in_hilfen_bot:
                    source = "hilfenbot"
                else:
                    source = "eurobot"

                # Enqueue as LOW priority (1) using our repository method.
                # We set commit=False so we can commit all records together at the end.
                await self.queue_repo.enqueue_low_priority(
                    user_id=user.user_id,
                    source=source,
                    commit=False
                )
                enqueued_count += 1
                
            except Exception as e:
                logger.error(f"Failed to enqueue cron sync for user {user.user_id}: {e}")

        # Commit all enqueued tasks in a single database transaction block
        await self.db.commit()
        
        logger.info(f"✅ CronSyncService completed. Enqueued {enqueued_count} low-priority sync tasks.")
        return {"status": "success", "enqueued_count": enqueued_count}
