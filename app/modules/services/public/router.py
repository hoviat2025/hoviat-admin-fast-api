"""Public (unauthenticated) service discovery API."""

from typing import List

from fastapi import APIRouter, Depends, Query, Request

from app.core.database import AsyncSessionLocal
from app.core.exceptions import ServiceError
from app.core.rate_limit import RateLimiter, make_rate_limit_dependency
from app.core.schemas import StandardResponse
from app.modules.services.schemas.service_requests import PublicServiceSearchParams
from app.modules.services.schemas.service_responses import ServiceResponse
from app.modules.services.search.facets_service import ServiceFacetsService
from app.modules.services.search.service_search_service import ServiceSearchService

router = APIRouter()

# Public search is unauthenticated, so it carries its own rate limit. The value
# mirrors the existing SNS profile search: enough for interactive browsing, low
# enough that an unbounded index-less ILIKE scan is not freely triggerable.
_search_limiter = RateLimiter(limit=60, window_seconds=60)
public_search_rate_limit = make_rate_limit_dependency(_search_limiter)


async def get_db_session():
    """
    Per-request session, always closed.

    A session created in a dependency and never closed leaks its pooled
    connection, which is exactly what SQLAlchemy's garbage-collector warning
    reports. Yielding inside a `with` block guarantees the connection returns to
    the pool on every path, including exceptions.
    """
    async with AsyncSessionLocal() as session:
        yield session


def get_service_search_service(
    session=Depends(get_db_session),
) -> ServiceSearchService:
    return ServiceSearchService(session)


def get_service_facets_service(
    session=Depends(get_db_session),
) -> ServiceFacetsService:
    return ServiceFacetsService(session)


def _reject_unknown_query_params(request: Request, allowed: set) -> None:
    """
    Refuse query parameters that are not part of the public contract.

    `PublicServiceSearchParams` sets `extra="forbid"`, but that alone is not
    enough: FastAPI builds a `Depends()` model from the DECLARED fields only, so
    an unrecognised query key is never passed into the schema and is silently
    dropped. The request would succeed and return unfiltered results.

    That is exactly the failure this endpoint must not have. A client that
    misspells `persian_language`, or sends `category_id` where the public
    parameter is `category`, would receive every service instead of an error, and
    nobody would notice because the response looks plausible.

    Repeating a parameter (?category=1&category=2) is legitimate, so the check
    compares parameter NAMES rather than parsed values.
    """
    unknown = sorted(set(request.query_params.keys()) - allowed)
    if unknown:
        raise ServiceError(
            "INVALID_INPUT",
            "Unsupported query parameter(s): "
            + ", ".join(unknown)
            + ". Supported: "
            + ", ".join(sorted(allowed)),
            422,
        )


@router.get(
    "/services/",
    response_model=StandardResponse[List[ServiceResponse]],
    summary="Search published services",
    description=(
        "Public discovery search. Returns published services only. The endpoint is "
        "international: it does not restrict the country, so the Germany-first "
        "frontend simply passes country_code=DE."
    ),
    dependencies=[Depends(public_search_rate_limit)],
)
async def search_public_services(
    request: Request,
    # `Query(...)` rather than `Depends()` on purpose. FastAPI does NOT bind a
    # List field on a `Depends()` model from the query string: `?category=5`
    # arrives as None, silently, so the filter would be ignored and the caller
    # would receive unfiltered results. Query() binds it properly, and the list
    # form lets a client repeat the parameter (?category=5&category=6).
    params: PublicServiceSearchParams = Query(default=None),
    search: ServiceSearchService = Depends(get_service_search_service),
):
    _reject_unknown_query_params(request, set(PublicServiceSearchParams.model_fields))

    rows, total = await search.public_search(params)
    meta = {
        "total": total,
        "page": params.page,
        "size": params.size,
        "pages": (total + params.size - 1) // params.size if total > 0 else 1,
    }
    return StandardResponse.success(data=rows, meta=meta)


@router.get(
    "/services/locations/",
    summary="Location choices available for public discovery",
    description=(
        "Country / first-level region / city hierarchy derived from the services "
        "that are actually published, so an empty branch never appears. "
        "International by construction: each country is a top-level branch, so the "
        "Germany-first frontend consumes the DE branch and another country needs "
        "no change here."
    ),
    dependencies=[Depends(public_search_rate_limit)],
)
async def service_locations(
    search: ServiceFacetsService = Depends(get_service_facets_service),
):
    return StandardResponse.success(data=await search.location_facets())