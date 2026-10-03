"""
Admin service listing search.

This is now a thin adapter over the shared query layer
(`app.modules.services.search`), which the public endpoint also uses. The admin
surface keeps its own richer contract — status filtering, owner and provenance
lookups, exact-name matching — while the query construction, category subtree
resolution, sorting and pagination all come from one implementation.

That is the point: the admin capability and the public capability cannot drift
apart, because there is only one place where a filter is turned into SQL.
"""

from typing import Optional, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.service import Service
from app.modules.services.schemas.service_requests import AdminServiceSearchParams
from app.modules.services.schemas.service_responses import ServiceResponse
from app.modules.services.search.service_search_service import ServiceSearchService


class ServiceAdminSearchRepository:
    """
    Admin-only service listing. This is deliberately NOT the public search: it
    exposes provenance and owner fields directly and performs no privacy
    redaction, because it exists so administrators can find and manage records.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self._search = ServiceSearchService(db)

    async def search_services(
        self, params: AdminServiceSearchParams
    ) -> tuple:
        return await self._search.admin_search(params)

    # Kept as a small shim so existing callers that pass loose keyword arguments
    # keep working while they migrate to the params object.
    async def search_services_legacy(
        self,
        q: Optional[str] = None,
        status: Optional[str] = None,
        city: Optional[str] = None,
        state: Optional[str] = None,
        country_code: Optional[str] = None,
        owner_user_id: Optional[int] = None,
        category_id: Optional[int] = None,
        persian_owned: Optional[str] = None,
        persian_provider: Optional[str] = None,
        persian_language: Optional[str] = None,
        persian_service: Optional[str] = None,
        source: Optional[str] = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple:
        from app.models.service import ServiceStatus

        return await self._search.admin_search(
            AdminServiceSearchParams(
                q=q,
                status=ServiceStatus(status) if status else None,
                city=city,
                state=state,
                country_code=country_code,
                owner_user_id=owner_user_id,
                category_id=category_id,
                persian_owned=persian_owned,
                persian_provider=persian_provider,
                persian_language=persian_language,
                persian_service=persian_service,
                source=source,
                page=page,
                size=size,
            )
        )