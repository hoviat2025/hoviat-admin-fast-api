from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from app.models.job_queue import JobQueue, JobStatus, JobPriority
from sqlalchemy import func


class JobQueueRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def enqueue_high_priority(self, user_id: int, source: str = "hilfen") -> None:
        stmt = (
            pg_insert(JobQueue)
            .values(
                user_id=user_id,
                priority=JobPriority.HIGH.value,
                status=JobStatus.PENDING,
                source=source,
            )
            .on_conflict_do_update(
                index_elements=[JobQueue.user_id],
                index_where=(JobQueue.status == JobStatus.PENDING),
                set_={
                    "priority": func.greatest(JobQueue.priority, JobPriority.HIGH.value),
                    "updated_at": func.now(),
                },
            )
        )
        await self.db.execute(stmt)
        await self.db.commit()

    async def enqueue_medium_priority(self, user_id: int, source: str = "eurobot") -> None:
        stmt = (
            pg_insert(JobQueue)
            .values(
                user_id=user_id,
                priority=JobPriority.MEDIUM.value,
                status=JobStatus.PENDING,
                source=source,
            )
            .on_conflict_do_update(
                index_elements=[JobQueue.user_id],
                index_where=(JobQueue.status == JobStatus.PENDING),
                set_={
                    "priority": func.greatest(JobQueue.priority, JobPriority.MEDIUM.value),
                    "updated_at": func.now(),
                },
            )
        )
        await self.db.execute(stmt)
        await self.db.commit()

    async def get_active_job(self, user_id: int, session: AsyncSession | None = None):
        s = session or self.db
        stmt = (
            select(JobQueue)
            .where(JobQueue.user_id == user_id)
            .where(JobQueue.status.in_([JobStatus.PENDING, JobStatus.PROCESSING]))
            .execution_options(populate_existing=True)
        )
        result = await s.execute(stmt)
        return result.scalars().first()

    async def get_latest_job(self, user_id: int, session: AsyncSession | None = None):
        s = session or self.db
        stmt = (
            select(JobQueue)
            .where(JobQueue.user_id == user_id)
            .order_by(JobQueue.id.desc())
            .limit(1)
            .execution_options(populate_existing=True)
        )
        result = await s.execute(stmt)
        return result.scalars().first()
