import asyncio
import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, update, func

# Database and Models
from app.core.database import AsyncSessionLocal
from app.models.job_queue import JobQueue, JobStatus, JobPriority

# Service to execute
from app.modules.eurobot.channels.services.update_channel_post_service import UpdateChannelPostService

logger = logging.getLogger(__name__)

async def run_queue_worker():
    """
    Continuous background loop that processes jobs from the job_queue table.
    Enforces a strict global rate limit of 6 tasks/minute, reserving slots for VIPs.
    """
    logger.info("🚀 Background queue worker loop initialized.")
    
    # 1. Recover Orphaned Jobs
    try:
        await reset_orphaned_jobs()
    except Exception as e:
        logger.error(f"Failed to reset orphaned jobs during startup: {e}")

    # 2. Main Processing Loop
    while True:
        try:
            async with AsyncSessionLocal() as session:
                
                # Fetch next candidate job without committing or locking yet
                job = await fetch_next_pending_job(session)
                
                if not job:
                    await asyncio.sleep(5)
                    continue

                # We have a candidate job! Check sliding-window limits
                limit_exceeded = await check_rate_limits(session, job.priority)
                
                if limit_exceeded:
                    await session.rollback()
                    await asyncio.sleep(2)
                    continue

                # Mark the job as 'processing' and commit immediately
                job.status = JobStatus.PROCESSING
                job.attempts += 1
                await session.commit()
                
                job_id = job.id
                user_id = job.user_id
                source = job.source

            # Run the actual heavy Telegram/DB syncing service
            await execute_job_task(job_id, user_id, source)

        except asyncio.CancelledError:
            logger.info("🛑 Queue worker received cancellation signal. Stopping cleanly.")
            break
        except Exception as e:
            logger.error(f"Error in queue worker execution loop: {e}", exc_info=True)
            await asyncio.sleep(5)


# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

async def reset_orphaned_jobs():
    """Resets any jobs stuck in 'processing' back to 'pending' on startup."""
    async with AsyncSessionLocal() as session:
        stmt = (
            update(JobQueue)
            .where(JobQueue.status == JobStatus.PROCESSING)
            .values(status=JobStatus.PENDING, error_message="Reset on worker startup")
        )
        result = await session.execute(stmt)
        await session.commit()
        
        rows_reset = result.rowcount
        if rows_reset > 0:
            logger.info(f"🔄 Recovered {rows_reset} orphaned jobs stuck in 'processing' status.")


async def fetch_next_pending_job(session) -> JobQueue | None:
    """Finds and locks the next candidate pending job sorted by priority and age."""
    stmt = (
        select(JobQueue)
        .where(JobQueue.status == JobStatus.PENDING)
        .order_by(JobQueue.priority.desc(), JobQueue.created_at.asc())
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    result = await session.execute(stmt)
    return result.scalars().first()


async def check_rate_limits(session, priority: int) -> bool:
    """
    Returns True if executing a job of the given priority would violate rate limits.
    - Global Limit: Max 6 total jobs completed in the last 60 seconds.
    - Non-VIP Cap: Max 3 low/medium jobs completed in the last 60 seconds.
    """
    one_minute_ago = datetime.now(timezone.utc) - timedelta(minutes=1)

    # 1. Check Global Limit (All completed jobs)
    stmt_total = (
        select(func.count(JobQueue.id))
        .where(
            JobQueue.status == JobStatus.COMPLETED,
            JobQueue.completed_at >= one_minute_ago
        )
    )
    total_completed = (await session.execute(stmt_total)).scalar() or 0
    if total_completed >= 6:
        return True

    # 2. Check Non-VIP Cap (If the next job is Low/Medium priority)
    if priority < JobPriority.HIGH.value:
        stmt_non_vip = (
            select(func.count(JobQueue.id))
            .where(
                JobQueue.status == JobStatus.COMPLETED,
                JobQueue.completed_at >= one_minute_ago,
                JobQueue.priority < JobPriority.HIGH.value
            )
        )
        non_vip_completed = (await session.execute(stmt_non_vip)).scalar() or 0
        if non_vip_completed >= 3:
            return True

    return False


async def execute_job_task(job_id: int, user_id: int, source: str):
    """Executes the UpdateChannelPostService and saves the final outcome."""
    logger.info(f"⚙️ Worker starting job {job_id} (User: {user_id}, Source: {source})")
    
    start_time = datetime.now()
    error_occurred = None
    
    async with AsyncSessionLocal() as session:
        try:
            service = UpdateChannelPostService(session)
            await service.execute(payload=user_id, update_source=source)
            
        except Exception as e:
            error_occurred = e
            logger.error(f"❌ Job {job_id} failed with error: {e}", exc_info=True)

        try:
            job = await session.get(JobQueue, job_id)
            if job:
                if error_occurred is None:
                    job.status = JobStatus.COMPLETED
                    job.completed_at = datetime.now(timezone.utc)
                    job.error_message = None
                    duration = (datetime.now() - start_time).total_seconds()
                    logger.info(f"✅ Job {job_id} completed successfully in {duration:.2f}s")
                else:
                    job.error_message = str(error_occurred)
                    if job.attempts >= job.max_attempts:
                        job.status = JobStatus.FAILED
                        logger.error(f"💀 Job {job_id} reached max retry limits and has FAILED.")
                    else:
                        job.status = JobStatus.PENDING
                        logger.warning(f"⚠️ Job {job_id} reset to pending for retry attempt {job.attempts + 1}.")
                
                await session.commit()
        except Exception as commit_err:
            logger.error(f"Failed to save outcome for job {job_id}: {commit_err}", exc_info=True)