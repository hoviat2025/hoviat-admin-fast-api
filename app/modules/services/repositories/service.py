from typing import Optional, Sequence

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.service import Service
from app.models.service_category import ServiceCategory
from app.modules.services.repositories.filters import relevance_condition
from app.modules.services.schemas.service_requests import TriStateFilter


class ServiceRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self, service_id: int) -> Optional[Service]:
        # populate_existing forces the freshly read row to overwrite the
        # instance already in the identity map. Without it, a read that follows
        # a Core UPDATE inside the same transaction returns the pre-update
        # values, because SQLAlchemy reuses the cached object and does not
        # refresh it. That silently returned stale data to admin API responses.
        result = await self.db.execute(
            select(Service)
            .where(Service.id == service_id)
            .execution_options(populate_existing=True)
        )
        return result.scalars().first()

    async def get_for_update(self, service_id: int) -> Optional[Service]:
        """
        Fetch the row with SELECT ... FOR UPDATE, so two admins saving the same
        service are serialised instead of interleaving their child writes.
        """
        result = await self.db.execute(
            select(Service)
            .where(Service.id == service_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return result.scalars().first()

    async def touch(self, service_id: int) -> None:
        """
        Bump the service's updated_at explicitly.

        Child-only mutations (contacts, categories) do not otherwise change the
        parent row, so without this the service's updated_at would not move when
        its aggregate changed and would stop being a usable version token.
        """
        await self.db.execute(
            update(Service)
            .where(Service.id == service_id)
            .values(updated_at=func.now())
        )

    async def get_full(self, service_id: int) -> Optional[Service]:
        """
        Fetch a service with its contacts and category links (and the category
        each link points at) eagerly loaded, so serialization never triggers a
        lazy load in an async context.
        """
        stmt = (
            select(Service)
            .where(Service.id == service_id)
            # See get(): refresh rather than reuse the cached instance, so a
            # read after a write in the same transaction sees the new values.
            .execution_options(populate_existing=True)
            .options(
                selectinload(Service.contacts),
                selectinload(Service.category_links).selectinload(
                    ServiceCategory.category
                ),
            )
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def create(self, data: dict) -> Service:
        service = Service(**data)
        self.db.add(service)
        await self.db.flush()
        return service

    async def update(self, service_id: int, data: dict) -> Optional[Service]:
        if data:
            await self.db.execute(
                update(Service).where(Service.id == service_id).values(**data)
            )
        return await self.get(service_id)

    async def exists_external(
        self, source: str, external_id: str, exclude_service_id: Optional[int] = None
    ) -> bool:
        """
        True when another service already carries this (source, external_id).
        The database index is the source of truth; this gives a friendly error
        before the insert fails.
        """
        stmt = select(Service.id).where(
            Service.source == source,
            Service.external_id == external_id,
        )
        if exclude_service_id is not None:
            stmt = stmt.where(Service.id != exclude_service_id)
        result = await self.db.execute(stmt.limit(1))
        return result.scalars().first() is not None

    async def list(
        self,
        q: Optional[str] = None,
        city: Optional[str] = None,
        state: Optional[str] = None,
        category_id: Optional[int] = None,
        status: Optional[str] = None,
        persian_owned: Optional[TriStateFilter] = None,
        persian_provider: Optional[TriStateFilter] = None,
        persian_language: Optional[TriStateFilter] = None,
        persian_service: Optional[TriStateFilter] = None,
        owner_user_id: Optional[int] = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[Sequence[Service], int]:
        """
        Optional, AND-ed filters. Today this backs the admin listing; the public
        search milestone will reuse the same query shape.
        """
        stmt = select(Service)

        if category_id is not None:
            stmt = stmt.join(
                ServiceCategory, ServiceCategory.service_id == Service.id
            ).where(ServiceCategory.category_id == category_id)

        conditions = []
        if q:
            pattern = f"%{q.strip()}%"
            conditions.append(
                or_(Service.name.ilike(pattern), Service.description.ilike(pattern))
            )
        if city:
            conditions.append(Service.city.ilike(f"%{city.strip()}%"))
        if state:
            # Case-insensitive exact match on the Bundesland, so "hessen" and
            # "Hessen" are the same filter rather than a substring coincidence.
            conditions.append(func.lower(Service.state) == state.strip().lower())
        if status is not None:
            conditions.append(Service.status == status)
        for column, filter_value in (
            (Service.persian_owned, persian_owned),
            (Service.persian_provider, persian_provider),
            (Service.persian_language, persian_language),
            (Service.persian_service, persian_service),
        ):
            condition = relevance_condition(column, filter_value)
            if condition is not None:
                conditions.append(condition)
        if owner_user_id is not None:
            conditions.append(Service.owner_user_id == owner_user_id)

        if conditions:
            stmt = stmt.where(and_(*conditions))

        # Stable ordering so paging does not reshuffle equal rows.
        stmt = stmt.order_by(Service.id.desc())

        count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
        total = await self.db.scalar(count_stmt)

        paginated = stmt.offset((page - 1) * size).limit(size)
        result = await self.db.execute(paginated)
        return result.scalars().all(), int(total or 0)
