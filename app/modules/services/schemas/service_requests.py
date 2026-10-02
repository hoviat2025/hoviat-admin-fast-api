from datetime import datetime, timezone
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.service import ServiceStatus
from app.models.service_contact import ServiceContactType


class ServiceContactInput(BaseModel):
    """One contact row supplied by an admin."""
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    type: ServiceContactType
    value: str = Field(min_length=1)
    platform: Optional[str] = None
    display_order: int = 0
    is_visible: bool = True


class ServiceCategoryInput(BaseModel):
    """
    One category assignment. `is_primary` marks the canonical category; at most
    one per service may be primary (validated on write).
    """
    model_config = ConfigDict(extra="forbid")

    category_id: int
    is_primary: bool = False


class ServiceCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=300)
    description: Optional[str] = None

    owner_user_id: Optional[int] = None
    # Private by default: adding an owner must not publish that relationship.
    # An admin must opt in explicitly.
    show_owner: bool = False

    persian_owned: bool = False
    persian_language: bool = False
    persian_service: bool = False

    address: Optional[str] = None
    postal_code: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    status: ServiceStatus = ServiceStatus.draft

    source: Optional[str] = None
    external_id: Optional[str] = None

    contacts: List[ServiceContactInput] = []
    categories: List[ServiceCategoryInput] = []


class ServiceUpdateRequest(BaseModel):
    """
    Partial update of a service's own fields. Contacts and categories are
    managed by their own endpoints, so they are not accepted here.
    """
    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = Field(default=None, min_length=1, max_length=300)
    description: Optional[str] = None

    owner_user_id: Optional[int] = None
    show_owner: Optional[bool] = None

    persian_owned: Optional[bool] = None
    persian_language: Optional[bool] = None
    persian_service: Optional[bool] = None

    address: Optional[str] = None
    postal_code: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    status: Optional[ServiceStatus] = None

    # Provenance can be corrected after creation. All-or-nothing and the
    # (source, external_id) uniqueness rule are enforced on update as well.
    source: Optional[str] = None
    external_id: Optional[str] = None


class ServiceStatusUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ServiceStatus


class ServiceAggregateSaveRequest(ServiceCreateRequest):
    """
    Full editable state of an existing service, applied in one transaction.

    Same shape as create, plus an optional optimistic-concurrency token: the
    `updated_at` the editor loaded. If the stored row has moved on since, the
    save is refused with 409 instead of overwriting someone else's work.

    Omit `expected_updated_at` to skip the optimistic check; the row lock still
    serialises writers.
    """

    expected_updated_at: Optional[str] = Field(
        default=None,
        description=(
            "The updated_at value the editor loaded. Supply it to detect a "
            "concurrent change; omit to only rely on the row lock."
        ),
    )

    @field_validator("expected_updated_at")
    @classmethod
    def _parse_expected(cls, value: Optional[str]) -> Optional[datetime]:
        if value is None or value == "":
            return None
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            raise ValueError("expected_updated_at must be an ISO-8601 timestamp")
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed


class ServiceContactsReplaceRequest(BaseModel):
    """Replace-all, mirroring PUT /account/social-links."""
    model_config = ConfigDict(extra="forbid")

    contacts: List[ServiceContactInput] = []


class ServiceCategoriesReplaceRequest(BaseModel):
    """Replace-all category assignments, including which one is primary."""
    model_config = ConfigDict(extra="forbid")

    categories: List[ServiceCategoryInput] = []


class ServiceSearchParams(BaseModel):
    """
    Optional, AND-ed filters for the admin listing today, and the basis of the
    public service search in a later milestone. Kept deliberately small for now.
    """
    model_config = ConfigDict(extra="ignore")

    q: Optional[str] = None
    city: Optional[str] = None
    category_id: Optional[int] = None
    status: Optional[ServiceStatus] = None
    persian_owned: Optional[bool] = None
    persian_language: Optional[bool] = None
    persian_service: Optional[bool] = None

    page: int = Field(default=1, ge=1)
    size: int = Field(default=20, ge=1, le=100)
