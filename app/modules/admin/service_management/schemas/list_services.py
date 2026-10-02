from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.service import ServiceStatus


class ServiceListMeta(BaseModel):
    """Pagination details placed in the StandardResponse `meta` field."""
    total: int
    page: int
    size: int
    pages: int


class ServiceListQuery(BaseModel):
    """
    Optional, AND-ed admin filters. Mirrors the admin `users-management` style:
    a global `q` plus exact/contains filters, all combined. This is the admin
    listing only; the public search (Milestone 4) is a separate mechanism.
    """
    model_config = ConfigDict(extra="ignore")

    q: Optional[str] = Field(
        default=None,
        description="Contains-match across name, description, city and address.",
    )
    status: Optional[ServiceStatus] = None
    city: Optional[str] = None
    owner_user_id: Optional[int] = None
    category_id: Optional[int] = None
    persian_owned: Optional[bool] = None
    persian_language: Optional[bool] = None
    persian_service: Optional[bool] = None
    source: Optional[str] = None

    page: int = Field(default=1, ge=1)
    size: int = Field(default=20, ge=1, le=100)


class OwnerAssignRequest(BaseModel):
    """Assign, replace, or (with null) clear a service's owner user."""
    model_config = ConfigDict(extra="forbid")

    owner_user_id: Optional[int] = None
