from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import case, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from app.models.job_queue import JobQueue, JobStatus, JobPriority


VALID_JOB_SOURCES = frozenset({"eurobot", "hilfenbot", "both"})


def merge_job_sources(existing_source: str, incoming_source: str) -> str:
    """Merge two validated queue sources without dropping either bot's work."""
    if existing_source == incoming_source:
        return existing_source
    if existing_source == "both" or incoming_source == "both":
        return "both"
    return "both"


class JobQueueRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def validate_source(source: str) -> None:
        if source not in VALID_JOB_SOURCES:
            raise ValueError(
                f"Invalid queue source {source!r}; expected one of "
                f"{sorted(VALID_JOB_SOURCES)}"
            )

    @staticmethod
    def source_merge_expression(incoming_source: str):
        """Return the SQL expression used when coalescing a pending job."""
        return case(
            (JobQueue.source == incoming_source, JobQueue.source),
            (JobQueue.source == "both", "both"),
            else_="both",
        )

    @staticmethod
    async def lock_user(session: AsyncSession, user_id: int) -> None:
        """Serialize queue state transitions for one user within a transaction."""
        await session.execute(select(func.pg_advisory_xact_lock(user_id)))

    async def _enqueue(
        self,
        *,
        user_id: int,
        priority: int,
        source: str,
        commit: bool,
    ) -> None:
        self.validate_source(source)
        await self.lock_user(self.db, user_id)

        stmt = (
            pg_insert(JobQueue)
            .values(
                user_id=user_id,
                priority=priority,
                status=JobStatus.PENDING,
                source=source,
            )
            .on_conflict_do_update(
                index_elements=[JobQueue.user_id],
                index_where=(JobQueue.status == JobStatus.PENDING),
                set_={
                    "priority": func.greatest(JobQueue.priority, priority),
                    "source": self.source_merge_expression(source),
                    "updated_at": func.now(),
                },
            )
        )
        await self.db.execute(stmt)
        if commit:
            await self.db.commit()

    async def enqueue_high_priority(
        self, user_id: int, source: str = "hilfenbot"
    ) -> None:
        await self._enqueue(
            user_id=user_id,
            priority=JobPriority.HIGH.value,
            source=source,
            commit=True,
        )

    async def enqueue_medium_priority(
        self, user_id: int, source: str = "eurobot"
    ) -> None:
        await self._enqueue(
            user_id=user_id,
            priority=JobPriority.MEDIUM.value,
            source=source,
            commit=True,
        )

    async def enqueue_low_priority(
        self, user_id: int, source: str = "eurobot", commit: bool = True
    ) -> None:
        await self._enqueue(
            user_id=user_id,
            priority=JobPriority.LOW.value,
            source=source,
            commit=commit,
        )

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
