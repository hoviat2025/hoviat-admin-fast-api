"""
Projection from admin/service rows into the public response schemas.

This is the ONLY place that converts a stored service into something a public
caller may see. Keeping the conversion here (rather than reusing the admin
serializer) means the public boundary is a short, auditable function instead of
"whatever the admin schema happens to contain".

Two rules are enforced structurally:

  * hidden contacts (`is_visible = false`) are never projected;
  * a retired (inactive) category is never projected, and never contributes to
    public matching.

The owner projection reuses the existing SNS privacy semantics rather than
inventing a second interpretation: the same `UserPrivacySettings` row, the same
global `is_profile_discoverable` failsafe, and the same per-field
`PrivacyScope.public` test that `SearchProfilesService` applies.
"""

from typing import List, Optional

from app.models.service import Service
from app.models.user_privacy_settings import PrivacyScope, UserPrivacySettings
from app.modules.sns.utils import assemble_profile_url
from app.modules.services.public.schemas import (
    PublicServiceCategory,
    PublicServiceContact,
    PublicServiceDetail,
    PublicServiceOwner,
    PublicServiceSummary,
)


def _public_categories(service: Service) -> List[PublicServiceCategory]:
    """
    Categories for a public consumer: active ones only.

    A service may legitimately still hold a retired category (admins keep them
    so history is not rewritten), but a retired category must not be presented
    as a way to find the service, and must not appear in its category list.
    """
    result: List[PublicServiceCategory] = []
    for link in service.category_links or []:
        category = link.category
        # A link whose category row is missing can only happen if the category
        # was hard-deleted; skip it rather than leaking a dangling id.
        if category is None or not category.is_active:
            continue
        result.append(
            PublicServiceCategory(
                id=category.id,
                name=category.name,
                slug=category.slug,
                is_primary=bool(link.is_primary),
            )
        )
    return result


def _public_contacts(service: Service) -> List[PublicServiceContact]:
    """Contacts with `is_visible = true` only."""
    return [
        PublicServiceContact(
            title=contact.title,
            type=contact.type,
            value=contact.value,
            platform=contact.platform,
            display_order=contact.display_order,
        )
        for contact in (service.contacts or [])
        if contact.is_visible
    ]


def _public_owner(
    service: Service, privacy: Optional[UserPrivacySettings]
) -> Optional[PublicServiceOwner]:
    """
    The service owner, if it may be shown publicly.

    Requires all three conditions from the product rule:

      1. the service has an owner,
      2. the service has `show_owner = true`,
      3. that user's privacy settings permit public display.

    For (3) the existing architecture expresses privacy *per field*, with a
    global `is_profile_discoverable` failsafe, and there is no single
    "identity may be shown" switch. So the same per-field test the public profile
    search uses is applied here: a name is included only if that specific field
    is `public`.

    If nothing survives the gate the owner is reported as absent rather than as
    an object of nulls, so the response never implies an owner exists.

    Note this returns no identifier of any kind. `owner_user_id` stays internal.
    """
    if not service.owner_user_id or not service.show_owner:
        return None

    user = service.owner
    if user is None:
        return None

    # Global failsafe: an undiscoverable profile is never projected, mirroring
    # SearchProfilesService.
    if privacy is None or not privacy.is_profile_discoverable:
        return None

    def allowed(scope: PrivacyScope) -> bool:
        return scope == PrivacyScope.public

    owner = PublicServiceOwner(
        username=user.username if allowed(privacy.username_visibility) else None,
        nickname=user.nickname if allowed(privacy.nickname_visibility) else None,
        first_name=user.first_name if allowed(privacy.first_name_visibility) else None,
        last_name=user.last_name if allowed(privacy.last_name_visibility) else None,
        profile_url=(
            assemble_profile_url(user.profile_path)
            if allowed(privacy.profile_picture_visibility) and user.profile_path
            else None
        ),
    )

    # Nothing is publicly shareable, so do not emit an empty owner object.
    if not any(
        (
            owner.username,
            owner.nickname,
            owner.first_name,
            owner.last_name,
            owner.profile_url,
        )
    ):
        return None

    return owner


def to_public_summary(service: Service) -> PublicServiceSummary:
    """Project a service into a search/list result. No contacts, no owner."""
    return PublicServiceSummary(
        id=service.id,
        name=service.name,
        description=service.description,
        persian_owned=service.persian_owned,
        persian_provider=service.persian_provider,
        persian_language=service.persian_language,
        persian_service=service.persian_service,
        address=service.address,
        postal_code=service.postal_code,
        city=service.city,
        state=service.state,
        country_code=service.country_code,
        latitude=service.latitude,
        longitude=service.longitude,
        categories=_public_categories(service),
    )


def to_public_detail(
    service: Service,
    privacy: Optional[UserPrivacySettings] = None,
) -> PublicServiceDetail:
    """
    Project a published service into a detail response.

    `privacy` is the OWNER's `UserPrivacySettings` row. It is passed in rather
    than read here so the caller controls the query and the session lifecycle.
    """
    summary = to_public_summary(service)
    return PublicServiceDetail(
        **summary.model_dump(),
        contacts=_public_contacts(service),
        owner=_public_owner(service, privacy),
        updated_at=service.updated_at,
    )