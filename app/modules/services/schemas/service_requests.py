import enum
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.service import ServiceStatus
from app.models.service_contact import ServiceContactType

# This directory lists services located in Germany. Used as the admin default so
# the field does not have to be typed every time, while remaining overridable.
DEFAULT_COUNTRY = "Germany"


class ServiceRelevanceUpdate(BaseModel):
    """
    Tri-state Iranian/Persian relevance values for a partial update.

    Every field is optional so an admin can change one signal without restating
    the others. A field that is present with a null value is an explicit "set to
    unknown"; a field that is absent is left untouched.
    """

    model_config = ConfigDict(extra="forbid")

    persian_owned: Optional[bool] = None
    persian_provider: Optional[bool] = None
    persian_language: Optional[bool] = None
    persian_service: Optional[bool] = None


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

    # Tri-state Iranian/Persian relevance. None means "not assessed", which is a
    # genuinely different answer from False, so these default to None rather
    # than False: a newly created listing should not claim to have been checked.
    persian_owned: Optional[bool] = None
    persian_provider: Optional[bool] = None
    persian_language: Optional[bool] = None
    persian_service: Optional[bool] = None

    # Location. Scope is Germany, so `country` defaults to it; `state` is the
    # Bundesland.
    address: Optional[str] = None
    postal_code: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = Field(default=DEFAULT_COUNTRY)
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

    Note that relevance fields use the `unset` sentinel: `None` cannot mean both
    "not supplied" and "set to unknown", so an explicit tri-state change is made
    by sending the field inside a `relevance` object rather than at the top
    level. See ServiceRelevanceUpdate.
    """
    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = Field(default=None, min_length=1, max_length=300)
    description: Optional[str] = None

    owner_user_id: Optional[int] = None
    show_owner: Optional[bool] = None

    # `relevance` carries the tri-state fields so that "set to unknown" is
    # expressible in a partial update. A key present with a null value sets the
    # column to unknown; an absent key leaves it untouched.
    relevance: Optional[ServiceRelevanceUpdate] = None

    address: Optional[str] = None
    postal_code: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
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

    Same shape as create, plus a REQUIRED optimistic-concurrency token: the
    `updated_at` the editor loaded. If the stored row has moved on since, the
    save is refused with 409 instead of overwriting someone else's work.

    The token is mandatory rather than optional on purpose. This endpoint
    replaces the whole editable aggregate of a record other people may also be
    editing, so a blind overwrite is the failure mode worth designing out; the
    row lock still serialises writers, but it cannot tell a legitimate save from
    a stale one.
    """

    expected_updated_at: datetime = Field(
        description=(
            "The updated_at value the editor loaded, as returned by the service "
            "read endpoints. Compared at millisecond precision."
        ),
    )


class ServiceContactsReplaceRequest(BaseModel):
    """Replace-all, mirroring PUT /account/social-links."""
    model_config = ConfigDict(extra="forbid")

    contacts: List[ServiceContactInput] = []


class ServiceCategoriesReplaceRequest(BaseModel):
    """Replace-all category assignments, including which one is primary."""
    model_config = ConfigDict(extra="forbid")

    categories: List[ServiceCategoryInput] = []


class TriStateFilter(str, enum.Enum):
    """
    Filter selector for a tri-state relevance column.

    Unlike an optional boolean, this can express "only the records nobody has
    assessed yet", which is a real data-quality question for curated imports.
    """

    yes = "yes"
    no = "no"
    unknown = "unknown"


class ServiceSearchParams(BaseModel):
    """
    Optional, AND-ed filters for the admin listing today, and the basis of the
    public service search in a later milestone.

    Location (state, city) and the four Iranian/Persian relevance signals are
    separate dimensions on purpose: "restaurants in Hessen with a Persian
    service" combines a German location with a relevance attribute, and must
    never be expressed as one geographic axis.
    """
    model_config = ConfigDict(extra="ignore")

    q: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    category_id: Optional[int] = None
    status: Optional[ServiceStatus] = None
    persian_owned: Optional[TriStateFilter] = None
    persian_provider: Optional[TriStateFilter] = None
    persian_language: Optional[TriStateFilter] = None
    persian_service: Optional[TriStateFilter] = None

    page: int = Field(default=1, ge=1)
    size: int = Field(default=20, ge=1, le=100)
