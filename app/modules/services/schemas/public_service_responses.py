"""Allow-listed public listing data, independent of admin response schemas."""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.service_contact import ServiceContactType
from app.modules.services.schemas.category_responses import CategorySummaryResponse


class PublicServiceContactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    title: str
    type: ServiceContactType
    value: str
    platform: Optional[str] = None
    display_order: int


class PublicServiceCategoryResponse(BaseModel):
    category_id: int
    is_primary: bool
    category: CategorySummaryResponse


class PublicCategoryTreeResponse(BaseModel):
    id: int
    name: str
    slug: str
    parent_id: Optional[int] = None
    parent_ids: list[int] = Field(default_factory=list)
    level: Literal[1, 2] = 1
    children: list["PublicCategoryTreeResponse"] = Field(default_factory=list)


class PublicServiceResponse(BaseModel):
    """Business information only; owner identity needs a separate privacy policy."""

    id: int
    name: str
    description: Optional[str] = None
    cover_image_url: Optional[str] = None
    persian_owned: Optional[bool] = None
    persian_provider: Optional[bool] = None
    persian_language: Optional[bool] = None
    persian_service: Optional[bool] = None
    address: Optional[str] = None
    postal_code: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country_code: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    created_at: datetime
    updated_at: datetime
    contacts: list[PublicServiceContactResponse] = Field(default_factory=list)
    categories: list[PublicServiceCategoryResponse] = Field(default_factory=list)
