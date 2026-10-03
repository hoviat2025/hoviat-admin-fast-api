"""
Public (unauthenticated) service response schemas.

Deliberately defined here, inside the public module, and NOT in the shared
`app/modules/services/schemas/service_responses.py`. The admin `ServiceResponse`
is the full record and is used by every admin write path; reusing it for a public
endpoint leaks admin-only fields (owner ids, provenance, hidden contacts) with no
compilation error and no failing test. Putting the public shapes in their own
module, and never importing the admin schema from a public route, makes that
mistake hard to make by accident.

Nothing here can be extended "to reuse the admin schema later" without it being
an obvious, reviewable act.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict

from app.models.service_contact import ServiceContactType


class PublicServiceCategory(BaseModel):
    """
    One category as public consumers see it.

    Only ACTIVE categories ever reach this schema: a retired category is an
    internal bookkeeping state and must not drive public discovery.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    is_primary: bool


class PublicServiceOwner(BaseModel):
    """
    A privacy-safe projection of the owning user.

    Carries no identifier of any kind. The raw owner id is never exposed: it is
    an internal relation into `users_eurobot`, and publishing it would let anyone
    enumerate user ids (and their existence) from the service directory.

    Every field is individually gated by that user's privacy settings, using the
    same per-field rule the existing public profile search applies. A field the
    owner has not made public is absent rather than blank-filled, so the
    response never implies a value exists.
    """

    model_config = ConfigDict(from_attributes=True)

    username: Optional[str] = None
    nickname: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    profile_url: Optional[str] = None


class PublicServiceContact(BaseModel):
    """
    A contact on the service detail page.

    `is_visible` is intentionally absent: this schema is only ever populated
    from contacts that are already visible, so exposing the flag would imply the
    hidden ones are being filtered rather than withheld, and would add a field
    with no meaning to a public consumer.
    """

    model_config = ConfigDict(from_attributes=True)

    title: str
    type: ServiceContactType
    value: str
    platform: Optional[str] = None
    display_order: int


class PublicServiceSummary(BaseModel):
    """
    A search/list result.

    Lean on purpose: a result list is fetched in bulk, and contacts do not belong
    there. They are on the detail endpoint instead.

    `status` is absent because the endpoint only ever returns published services,
    so echoing it back to the caller would be redundant reassurance rather than
    information.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: Optional[str] = None

    # Tri-state Iranian/Persian relevance. None means "not assessed", which a
    # public consumer must be able to distinguish from False.
    persian_owned: Optional[bool] = None
    persian_provider: Optional[bool] = None
    persian_language: Optional[bool] = None
    persian_service: Optional[bool] = None

    # Public location. Coordinates are included because a map view is a core part
    # of local discovery and the values are already public on the record.
    address: Optional[str] = None
    postal_code: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country_code: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    categories: List[PublicServiceCategory] = []


class PublicServiceDetail(PublicServiceSummary):
    """
    A single published service.

    Extends the summary with the things that belong on one record rather than on
    a list: visible contacts, a privacy-gated owner, and when it last changed.

    `updated_at` is included here (and not in the summary) because freshness is
    meaningful on a detail page and meaningless in a result list.
    """

    contacts: List[PublicServiceContact] = []
    owner: Optional[PublicServiceOwner] = None
    updated_at: Optional[datetime] = None


class PublicCategoryNode(BaseModel):
    """
    One node of the public category hierarchy.

    `parent_id` is null for a root node. An active category whose parent is
    inactive is presented as a root: it must stay reachable, otherwise the
    active child would vanish from public navigation entirely just because an
    ancestor was retired.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    display_order: int = 0
    parent_id: Optional[int] = None
    children: List["PublicCategoryNode"] = []


PublicCategoryNode.model_rebuild()


# Names a reviewer can grep for when auditing what the public surface exposes.
# Anything absent from these tuples is, by construction, not public.
PUBLIC_SUMMARY_FIELDS = tuple(PublicServiceSummary.model_fields)
PUBLIC_DETAIL_FIELDS = tuple(PublicServiceDetail.model_fields)