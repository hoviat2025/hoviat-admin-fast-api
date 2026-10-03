from typing import List, Optional

from fastapi import Query
from pydantic import BaseModel, ConfigDict, Field

from app.core.exceptions import ServiceError
from app.models.service import ServiceStatus
from app.modules.services.schemas.service_requests import (
    AdminServiceSearchParams,
    TriStateFilter,
)


class ServiceListMeta(BaseModel):
    """Pagination details placed in the StandardResponse `meta` field."""
    total: int
    page: int
    size: int
    pages: int


class ServiceListQuery(BaseModel):
    """
    Query parameters for the admin service listing.

    This is the HTTP-facing shape (query strings arrive as strings, so ids are
    strings here). `to_search_params()` converts it into the typed
    `AdminServiceSearchParams` the shared query layer consumes, which is where
    validation of ids and enum values happens with proper error messages.

    Note the location/relevance independence: `state`, `city`, `country_code` and
    the four relevance signals are separate dimensions. Nothing here implies a
    geographic value from a relevance value, or the reverse.
    """

    model_config = ConfigDict(extra="ignore")

    q: Optional[str] = Field(
        default=None,
        description="Contains-match across name, description, city, state, category name and slug.",
    )
    status: Optional[ServiceStatus] = None
    country_code: Optional[str] = Field(
        default=None, description="ISO-3166-1 alpha-2 code, e.g. DE."
    )
    city: Optional[str] = None
    state: Optional[str] = Field(
        default=None,
        description="First-level region in canonical spelling, case-insensitive exact.",
    )
    owner_user_id: Optional[str] = None
    category_id: Optional[str] = None
    # Query() rather than a bare List: FastAPI does not bind a List field on a
    # Depends() model from the query string, so it would silently arrive empty.
    category_ids: Optional[List[str]] = Query(default=None)
    category_primary_only: bool = False
    postal_code: Optional[str] = None
    name: Optional[str] = None
    persian_owned: Optional[TriStateFilter] = None
    persian_provider: Optional[TriStateFilter] = None
    persian_language: Optional[TriStateFilter] = None
    persian_service: Optional[TriStateFilter] = None
    source: Optional[str] = None
    sort: str = "newest"

    page: int = Field(default=1, ge=1)
    size: int = Field(default=20, ge=1, le=100)

    def to_search_params(self) -> AdminServiceSearchParams:
        """Convert the string-typed query shape into the typed search params."""
        return AdminServiceSearchParams(
            q=self.q,
            status=self.status,
            country_code=self.country_code,
            city=self.city,
            state=self.state,
            postal_code=self.postal_code,
            name=self.name,
            owner_user_id=_optional_int(self.owner_user_id, "owner_user_id"),
            category_id=_optional_int(self.category_id, "category_id"),
            category_ids=_optional_int_list(self.category_ids, "category_ids"),
            category_primary_only=self.category_primary_only,
            persian_owned=self.persian_owned,
            persian_provider=self.persian_provider,
            persian_language=self.persian_language,
            persian_service=self.persian_service,
            source=self.source,
            sort=self.sort,
            page=self.page,
            size=self.size,
        )


def _optional_int(value: Optional[str], field: str) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(str(value).strip())
    except ValueError:
        raise ServiceError("INVALID_INPUT", f"{field} must be an integer", 422)


def _optional_int_list(values: Optional[List[str]], field: str) -> Optional[List[int]]:
    if not values:
        return None
    return [_optional_int(value, field) for value in values]


class OwnerAssignRequest(BaseModel):
    """Assign, replace, or (with null) clear a service's owner user."""
    model_config = ConfigDict(extra="forbid")

    owner_user_id: Optional[int] = None
