"""The owner's editable business fields, separate from staff moderation."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.service import ServiceStatus
from app.modules.services.schemas.service_requests import ServiceContactInput
from app.modules.services.schemas.service_responses import (
    ServiceCategoryResponse,
    ServiceContactResponse,
    ServiceResponse,
)


class OwnedServiceUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_updated_at: datetime
    name: Optional[str] = Field(default=None, min_length=1, max_length=300)
    description: Optional[str] = None
    owner_show_profile: Optional[bool] = None
    address: Optional[str] = None
    postal_code: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country_code: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    # Omission preserves all contacts; [] explicitly removes them all.
    contacts: Optional[list[ServiceContactInput]] = None

    @model_validator(mode="after")
    def reject_null_required_fields(self):
        for field in ("name", "owner_show_profile", "contacts"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class OwnedServiceResponse(BaseModel):
    """Includes private business contacts for editing, never import metadata."""

    id: int
    name: str
    description: Optional[str] = None
    cover_image_url: Optional[str] = None
    show_owner: bool
    owner_show_profile: bool = False
    admin_allows_owner_visibility: bool = False
    status: ServiceStatus
    address: Optional[str] = None
    postal_code: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country_code: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    persian_owned: Optional[bool] = None
    persian_provider: Optional[bool] = None
    persian_language: Optional[bool] = None
    persian_service: Optional[bool] = None
    contacts: list[ServiceContactResponse] = Field(default_factory=list)
    categories: list[ServiceCategoryResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_service(cls, service: ServiceResponse):
        data = service.model_dump(include=set(cls.model_fields))
        data["admin_allows_owner_visibility"] = service.show_owner
        return cls.model_validate(data)
