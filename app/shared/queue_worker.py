import asyncio
import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, update, func, or_, and_
from sqlalchemy.orm import aliased

# Database and Models
from app.core.database import AsyncSessionLocal
from app.models.job_queue import JobQueue, JobStatus, JobPriority

# Service to execute
from app.modules.eurobot.channels.services.update_channel_post_service import UpdateChannelPostService

logger = logging.getLogger(__name__)

# ==============================================================================
# CONFIGURABLE RATE LIMITS (Sliding 60-second window)
# ==============================================================================
BACKGROUND_LANE_LIMIT = 3   # Max low/medium priority jobs completed per minute
VIP_LANE_LIMIT = 3          # Max high priority (VIP) jobs completed per minute


async def run_vip_queue_worker():
    """Runs the dedicated worker for HIGH priority (VIP) jobs."""
    await run_worker_lane(is_vip=True, lane_name="VIP Lane")


async def run_background_queue_worker():
    """Runs the dedicated worker for LOW and MEDIUM priority background jobs."""
    # Only reset orphaned jobs once on startup
    try:
        await reset_orphaned_jobs()
    except Exception as e:
        logger.error(f"Failed to reset orphaned jobs during startup: {e}")
        
    await run_worker_lane(is_vip=False, lane_name="Background Lane")


# ==============================================================================
# GENERIC WORKER RUNNER
# ==============================================================================

async def run_worker_lane(is_vip: bool, lane_name: str):
    """
    Generic execution loop runner for a specific priority lane.
    """
    logger.info(f"🚀 {lane_name} worker loop initialized.")
    
    while True:
        try:
            async with AsyncSessionLocal() as session:
                
                # Fetch next candidate job for this specific lane
                job = await fetch_next_pending_job(session, is_vip=is_vip)
                
                if not job:
                    await asyncio.sleep(5)
                    continue

                # Check sliding-window rate limits for this specific lane
                limit_exceeded = await check_rate_limits(session, is_vip=is_vip)
                
                if limit_exceeded:
                    await session.rollback()
                    await asyncio.sleep(2)
                    continue

                # Mark the job as 'processing' and commit immediately
                job.status = JobStatus.PROCESSING
                job.attempts += 1
                job.updated_at = datetime.now(timezone.utc) # <-- Explicitly set attempt start time
                await session.commit()
                
                job_id = job.id
                user_id = job.user_id
                source = job.source

            # Run the actual heavy Telegram/DB syncing service (Non-blocking to other lane)
            await execute_job_task(job_id, user_id, source)

        except asyncio.CancelledError:
            logger.info(f"🛑 {lane_name} received cancellation signal. Stopping cleanly.")
            break
        except Exception as e:
            logger.error(f"Error in {lane_name} execution loop: {e}", exc_info=True)
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


async def fetch_next_pending_job(session, is_vip: bool) -> JobQueue | None:
    """
    Finds and locks the next candidate pending job sorted by priority and age.
    Filters selection based on whether the lane is configured for VIPs or Background tasks.
    """
    jq_alias = aliased(JobQueue)
    
    # Subquery checking if a 'processing' job already exists for the same user
    processing_exists = (
        select(1)
        .where(
            jq_alias.user_id == JobQueue.user_id,
            jq_alias.status == JobStatus.PROCESSING
        )
        .exists()
    )
    
    # Lane isolation logic
    if is_vip:
        priority_filter = JobQueue.priority >= JobPriority.HIGH.value
    else:
        priority_filter = JobQueue.priority < JobPriority.HIGH.value
    
    # Fetch the next pending job ONLY if no other job for the same user is currently processing
    stmt = (
        select(JobQueue)
        .where(
            JobQueue.status == JobStatus.PENDING,
            priority_filter,
            ~processing_exists  # NOT EXISTS processing job for the same user
        )
        .order_by(JobQueue.priority.desc(), JobQueue.created_at.asc())
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    result = await session.execute(stmt)
    return result.scalars().first()


async def check_rate_limits(session, is_vip: bool) -> bool:
    """
    Returns True if executing a job in the given lane would violate its specific limits.
    Counts all attempts (completed, failed, or retries) made in the last 60 seconds.
    """
    one_minute_ago = datetime.now(timezone.utc) - timedelta(minutes=1)

    # Base filter to isolate VIP vs Background lanes
    if is_vip:
        lane_filter = JobQueue.priority >= JobPriority.HIGH.value
        limit = VIP_LANE_LIMIT
    else:
        lane_filter = JobQueue.priority < JobPriority.HIGH.value
        limit = BACKGROUND_LANE_LIMIT

    # Query to count any job attempted in the last 60 seconds:
    # - JobStatus.COMPLETED (Successfully done)
    # - JobStatus.FAILED (Permanently dead)
    # - JobStatus.PROCESSING (Currently active)
    # - JobStatus.PENDING with attempts > 0 (Failed and reset for a retry)
    stmt = (
        select(func.count(JobQueue.id))
        .where(
            lane_filter,
            JobQueue.updated_at >= one_minute_ago,
            or_(
                JobQueue.status.in_([JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.PROCESSING]),
                and_(
                    JobQueue.status == JobStatus.PENDING,
                    JobQueue.attempts > 0
                )
            )
        )
    )
    completed_count = (await session.execute(stmt)).scalar() or 0
    if completed_count >= limit:
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
                # Explicitly update the modification timestamp on completion/failure
                job.updated_at = datetime.now(timezone.utc)
                
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