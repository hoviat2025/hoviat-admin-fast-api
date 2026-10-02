from typing import Optional, Sequence

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.service import Service
from app.models.service_category import ServiceCategory


class ServiceRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self, service_id: int) -> Optional[Service]:
        result = await self.db.execute(
            select(Service).where(Service.id == service_id)
        )
        return result.scalars().first()

    async def get_full(self, service_id: int) -> Optional[Service]:
        """
        Fetch a service with its contacts and category links (and the category
        each link points at) eagerly loaded, so serialization never triggers a
        lazy load in an async context.
        """
        stmt = (
            select(Service)
            .where(Service.id == service_id)
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
        category_id: Optional[int] = None,
        status: Optional[str] = None,
        persian_owned: Optional[bool] = None,
        persian_language: Optional[bool] = None,
        persian_service: Optional[bool] = None,
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
        if status is not None:
            conditions.append(Service.status == status)
        if persian_owned is not None:
            conditions.append(Service.persian_owned == persian_owned)
        if persian_language is not None:
            conditions.append(Service.persian_language == persian_language)
        if persian_service is not None:
            conditions.append(Service.persian_service == persian_service)
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
