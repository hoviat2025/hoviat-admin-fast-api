import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import aliased

from app.core.database import AsyncSessionLocal
from app.models.job_queue import JobPriority, JobQueue, JobStatus
from app.modules.eurobot.channels.services.update_channel_post_service import (
    UpdateChannelPostService,
)
from app.shared.repositories.job_queue import (
    JobQueueRepository,
    merge_job_sources,
)

logger = logging.getLogger(__name__)

# Sliding 60-second lane limits.
BACKGROUND_LANE_LIMIT = 3
VIP_LANE_LIMIT = 3


async def run_vip_queue_worker():
    """Run the dedicated worker for high-priority jobs."""
    await run_worker_lane(is_vip=True, lane_name="VIP Lane")


async def run_background_queue_worker():
    """Run the dedicated worker for low- and medium-priority jobs."""
    await run_worker_lane(is_vip=False, lane_name="Background Lane")


async def run_worker_lane(is_vip: bool, lane_name: str):
    """Continuously execute one job at a time for a priority lane."""
    logger.info("%s worker loop initialized.", lane_name)

    while True:
        try:
            async with AsyncSessionLocal() as session:
                job = await fetch_next_pending_job(session, is_vip=is_vip)

                if not job:
                    await asyncio.sleep(5)
                    continue

                if await check_rate_limits(session, is_vip=is_vip):
                    await session.rollback()
                    await asyncio.sleep(2)
                    continue

                # Commit the state change before performing external work.
                job.status = JobStatus.PROCESSING
                job.attempts += 1
                job.updated_at = datetime.now(timezone.utc)
                await session.commit()

                job_id = job.id
                user_id = job.user_id
                source = job.source

            await execute_job_task(job_id, user_id, source)

        except asyncio.CancelledError:
            logger.info("%s received cancellation; stopping.", lane_name)
            break
        except Exception:
            logger.exception("Error in %s execution loop.", lane_name)
            await asyncio.sleep(5)


def append_job_error(existing_error: str | None, message: str) -> str:
    """Preserve earlier failure context while adding the latest queue decision."""
    if not existing_error:
        return message
    return f"{existing_error}\n{message}"


async def resolve_processing_job_failure(
    *,
    job_id: int,
    user_id: int,
    failure_message: str,
    recovery_mode: bool = False,
) -> str | None:
    """
    Resolve a failed or abandoned processing job without creating a second
    pending row for the user.

    Returns the processing row's resulting status, or None if that row is no
    longer processing.
    """
    async with AsyncSessionLocal() as session:
        # Enqueues and failure resolution use the same per-user transaction lock.
        await JobQueueRepository.lock_user(session, user_id)

        job_stmt = (
            select(JobQueue)
            .where(
                JobQueue.id == job_id,
                JobQueue.user_id == user_id,
                JobQueue.status == JobStatus.PROCESSING,
            )
            .with_for_update()
        )
        job = (await session.execute(job_stmt)).scalars().first()
        if not job:
            await session.rollback()
            return None

        successor_stmt = (
            select(JobQueue)
            .where(
                JobQueue.user_id == user_id,
                JobQueue.status == JobStatus.PENDING,
                JobQueue.id != job_id,
            )
            .order_by(JobQueue.id.asc())
            .limit(1)
            .with_for_update()
        )
        successor = (await session.execute(successor_stmt)).scalars().first()

        now = datetime.now(timezone.utc)
        job_error = append_job_error(job.error_message, failure_message)

        if successor:
            # The successor represents updates received while this job ran.
            # Preserve all required work, then close the older processing row.
            successor.priority = max(successor.priority, job.priority)
            successor.source = merge_job_sources(successor.source, job.source)
            successor.updated_at = now

            context = (
                "startup recovery" if recovery_mode else "runtime failure handling"
            )
            job.status = JobStatus.FAILED
            job.error_message = append_job_error(
                job_error,
                f"Superseded by pending job {successor.id} during {context}",
            )
        elif job.attempts >= job.max_attempts:
            job.status = JobStatus.FAILED
            job.error_message = append_job_error(
                job_error,
                f"Maximum attempts reached ({job.attempts}/{job.max_attempts})",
            )
        else:
            job.status = JobStatus.PENDING
            job.error_message = job_error

        job.updated_at = now
        await session.commit()
        return job.status


async def recover_orphaned_jobs() -> None:
    """Resolve processing rows left behind by the previous application process."""
    async with AsyncSessionLocal() as session:
        stmt = (
            select(JobQueue.id, JobQueue.user_id)
            .where(JobQueue.status == JobStatus.PROCESSING)
            .order_by(JobQueue.id.asc())
        )
        orphaned_jobs = (await session.execute(stmt)).all()

    if not orphaned_jobs:
        logger.info("Queue startup recovery found no abandoned processing jobs.")
        return

    logger.info(
        "Queue startup recovery found %s abandoned processing job(s).",
        len(orphaned_jobs),
    )
    requeued_count = 0
    closed_count = 0

    for job_id, user_id in orphaned_jobs:
        resulting_status = await resolve_processing_job_failure(
            job_id=job_id,
            user_id=user_id,
            failure_message="Interrupted by application restart",
            recovery_mode=True,
        )
        if resulting_status == JobStatus.PENDING:
            requeued_count += 1
        elif resulting_status == JobStatus.FAILED:
            closed_count += 1

    logger.info(
        "Queue startup recovery completed: %s requeued, %s closed.",
        requeued_count,
        closed_count,
    )


async def fetch_next_pending_job(session, is_vip: bool) -> JobQueue | None:
    """
    Lock the next pending job for one lane, excluding users who already have a
    processing job.
    """
    jq_alias = aliased(JobQueue)
    processing_exists = (
        select(1)
        .where(
            jq_alias.user_id == JobQueue.user_id,
            jq_alias.status == JobStatus.PROCESSING,
        )
        .exists()
    )

    if is_vip:
        priority_filter = JobQueue.priority >= JobPriority.HIGH.value
    else:
        priority_filter = JobQueue.priority < JobPriority.HIGH.value

    stmt = (
        select(JobQueue)
        .where(
            JobQueue.status == JobStatus.PENDING,
            priority_filter,
            ~processing_exists,
        )
        .order_by(JobQueue.priority.desc(), JobQueue.created_at.asc())
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    result = await session.execute(stmt)
    return result.scalars().first()


async def check_rate_limits(session, is_vip: bool) -> bool:
    """Return whether the lane has exhausted its sliding 60-second allowance."""
    one_minute_ago = datetime.now(timezone.utc) - timedelta(minutes=1)

    if is_vip:
        lane_filter = JobQueue.priority >= JobPriority.HIGH.value
        limit = VIP_LANE_LIMIT
    else:
        lane_filter = JobQueue.priority < JobPriority.HIGH.value
        limit = BACKGROUND_LANE_LIMIT

    stmt = (
        select(func.count(JobQueue.id))
        .where(
            lane_filter,
            JobQueue.updated_at >= one_minute_ago,
            or_(
                JobQueue.status.in_(
                    [
                        JobStatus.COMPLETED,
                        JobStatus.FAILED,
                        JobStatus.PROCESSING,
                    ]
                ),
                and_(
                    JobQueue.status == JobStatus.PENDING,
                    JobQueue.attempts > 0,
                ),
            ),
        )
    )
    attempted_count = (await session.execute(stmt)).scalar() or 0
    return attempted_count >= limit


async def execute_job_task(job_id: int, user_id: int, source: str):
    """Execute one synchronization job and persist its final queue outcome."""
    logger.info(
        "Worker starting job %s (user=%s, source=%s).",
        job_id,
        user_id,
        source,
    )

    start_time = datetime.now()
    error_occurred = None

    async with AsyncSessionLocal() as session:
        try:
            service = UpdateChannelPostService(session)
            await service.execute(payload=user_id, update_source=source)
        except Exception as exc:
            error_occurred = exc
            logger.exception("Job %s failed: %s", job_id, exc)
            # A failed SQL operation may have invalidated the service transaction.
            await session.rollback()

        if error_occurred is None:
            try:
                job = await session.get(JobQueue, job_id)
                if not job:
                    logger.warning(
                        "Job %s disappeared before its successful outcome was saved.",
                        job_id,
                    )
                    return

                job.updated_at = datetime.now(timezone.utc)
                job.status = JobStatus.COMPLETED
                job.completed_at = datetime.now(timezone.utc)
                job.error_message = None
                await session.commit()

                duration = (datetime.now() - start_time).total_seconds()
                logger.info("Job %s completed in %.2fs.", job_id, duration)
            except Exception as exc:
                logger.exception(
                    "Failed to save successful outcome for job %s.",
                    job_id,
                )
                await session.rollback()
                error_occurred = exc
            else:
                return

    try:
        resulting_status = await resolve_processing_job_failure(
            job_id=job_id,
            user_id=user_id,
            failure_message=str(error_occurred),
        )
        if resulting_status == JobStatus.PENDING:
            logger.warning("Job %s returned to pending for another attempt.", job_id)
        elif resulting_status == JobStatus.FAILED:
            logger.error("Job %s was closed after failure.", job_id)
        else:
            logger.warning(
                "Job %s was no longer processing during failure handling.",
                job_id,
            )
    except Exception:
        logger.exception("Failed to save failed outcome for job %s.", job_id)
