from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict

from app.models.service import ServiceStatus
from app.models.service_contact import ServiceContactType
from app.modules.services.schemas.category_responses import CategorySummaryResponse


class ServiceContactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    type: ServiceContactType
    value: str
    platform: Optional[str] = None
    display_order: int
    is_visible: bool


class ServiceCategoryResponse(BaseModel):
    """A category assignment plus the category it points at."""
    category_id: int
    is_primary: bool
    category: Optional[CategorySummaryResponse] = None


class ServiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int

    owner_user_id: Optional[int] = None
    show_owner: bool

    name: str
    description: Optional[str] = None

    # Tri-state Iranian/Persian relevance: true = explicitly yes,
    # false = explicitly no, null = not assessed. These describe the listing,
    # not its location.
    persian_owned: Optional[bool] = None
    persian_provider: Optional[bool] = None
    persian_language: Optional[bool] = None
    persian_service: Optional[bool] = None

    # Location; scope is Germany, so `state` is the Bundesland.
    address: Optional[str] = None
    postal_code: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country_code: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    status: ServiceStatus

    source: Optional[str] = None
    external_id: Optional[str] = None

    created_at: datetime
    updated_at: datetime

    contacts: List[ServiceContactResponse] = []
    categories: List[ServiceCategoryResponse] = []
