from typing import Optional, Sequence

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.service import Service
from app.models.service_category import ServiceCategory
from app.modules.services.repositories.filters import relevance_condition
from app.modules.services.schemas.service_requests import TriStateFilter


class ServiceAdminSearchRepository:
    """
    Admin-only service listing. This is deliberately NOT the public search
    (Milestone 4): it has no privacy redaction, exposes provenance and owner
    fields directly, and exists so administrators can find and manage records.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def search_services(
        self,
        q: Optional[str] = None,
        status: Optional[str] = None,
        city: Optional[str] = None,
        state: Optional[str] = None,
        owner_user_id: Optional[int] = None,
        category_id: Optional[int] = None,
        persian_owned: Optional[TriStateFilter] = None,
        persian_provider: Optional[TriStateFilter] = None,
        persian_language: Optional[TriStateFilter] = None,
        persian_service: Optional[TriStateFilter] = None,
        source: Optional[str] = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[Sequence[Service], int]:
        stmt = select(Service)

        if category_id is not None:
            stmt = stmt.join(
                ServiceCategory, ServiceCategory.service_id == Service.id
            ).where(ServiceCategory.category_id == category_id)

        conditions = []
        if q:
            pattern = f"%{q.strip()}%"
            conditions.append(
                or_(
                    Service.name.ilike(pattern),
                    Service.description.ilike(pattern),
                    Service.city.ilike(pattern),
                    Service.state.ilike(pattern),
                    Service.address.ilike(pattern),
                )
            )
        if status is not None:
            conditions.append(Service.status == status)
        if city:
            conditions.append(Service.city.ilike(f"%{city.strip()}%"))
        if state:
            conditions.append(func.lower(Service.state) == state.strip().lower())
        if owner_user_id is not None:
            conditions.append(Service.owner_user_id == owner_user_id)
        # Location filters and relevance filters stay independent: filtering by
        # Bundesland must never imply anything about Iranian/Persian relevance,
        # and vice versa.
        for column, filter_value in (
            (Service.persian_owned, persian_owned),
            (Service.persian_provider, persian_provider),
            (Service.persian_language, persian_language),
            (Service.persian_service, persian_service),
        ):
            condition = relevance_condition(column, filter_value)
            if condition is not None:
                conditions.append(condition)
        if source:
            conditions.append(Service.source == source)

        if conditions:
            stmt = stmt.where(and_(*conditions))

        # Stable ordering (newest first) for predictable paging.
        stmt = stmt.order_by(Service.id.desc())

        count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
        total = await self.db.scalar(count_stmt)

        paginated = (
            stmt.options(
                selectinload(Service.contacts),
                selectinload(Service.category_links).selectinload(
                    ServiceCategory.category
                ),
            )
            .offset((page - 1) * size)
            .limit(size)
        )
        result = await self.db.execute(paginated)
        return result.scalars().all(), int(total or 0)
