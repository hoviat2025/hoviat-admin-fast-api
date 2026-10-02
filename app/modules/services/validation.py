"""
Pure validation helpers for the service-directory domain.

Kept free of database access so the rules can be unit-tested in isolation: the
caller supplies any lookup the rule needs (for example the parent map used for
cycle detection). Functions raise ServiceError, matching the project's
convention for business-rule failures.
"""

import re
from datetime import datetime
from typing import Callable, Optional, Sequence

from app.core.exceptions import ServiceError
from app.models.service import ServiceStatus

_SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def normalise_slug(value: Optional[str]) -> str:
    """
    Canonicalise a slug: trimmed, lowercased, spaces/underscores to hyphens.
    Slugs are URL identifiers, so they stay ASCII and hyphen-separated.
    """
    slug = (value or "").strip().lower()
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    if not slug:
        raise ServiceError("INVALID_INPUT", "slug is required", 422)
    if not _SLUG_PATTERN.match(slug):
        raise ServiceError(
            "INVALID_INPUT",
            "slug may contain only lowercase latin letters, digits and hyphens",
            422,
        )
    return slug


def clean_optional_text(value: Optional[str]) -> Optional[str]:
    """
    Trim a free-text field and turn an empty result into None, so "" and an
    omitted value are stored the same way.
    """
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed or None


def require_non_empty(value: Optional[str], field: str) -> str:
    trimmed = (value or "").strip()
    if not trimmed:
        raise ServiceError("INVALID_INPUT", f"{field} is required", 422)
    return trimmed


def validate_latitude(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    if not -90.0 <= float(value) <= 90.0:
        raise ServiceError(
            "INVALID_INPUT", "latitude must be between -90 and 90", 422
        )
    return float(value)


def validate_longitude(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    if not -180.0 <= float(value) <= 180.0:
        raise ServiceError(
            "INVALID_INPUT", "longitude must be between -180 and 180", 422
        )
    return float(value)


def validate_location_pair(
    latitude: Optional[float], longitude: Optional[float]
) -> None:
    """A coordinate is only useful as a pair; one without the other is a bug."""
    if (latitude is None) != (longitude is None):
        raise ServiceError(
            "INVALID_INPUT",
            "latitude and longitude must be provided together",
            422,
        )


def validate_provenance(
    source: Optional[str], external_id: Optional[str]
) -> tuple[Optional[str], Optional[str]]:
    """
    Import provenance is all-or-nothing: a stable external identity needs both
    the source it came from and the id within that source.
    """
    source = clean_optional_text(source)
    external_id = clean_optional_text(external_id)

    if (source is None) != (external_id is None):
        raise ServiceError(
            "INVALID_INPUT",
            "source and external_id must be provided together",
            422,
        )
    return source, external_id


def validate_contact_fields(
    title: Optional[str], value: Optional[str]
) -> tuple[str, str]:
    return (
        require_non_empty(title, "contact title"),
        require_non_empty(value, "contact value"),
    )


def resolve_primary_category(category_ids: Sequence[tuple[int, bool]]) -> Optional[int]:
    """
    Given (category_id, is_primary) pairs, return the primary category id.

    Enforces at most one primary. "Exactly one primary when categories exist"
    is enforced separately by validate_category_selection, because a draft may
    legitimately have no categories at all.
    """
    primaries = [category_id for category_id, is_primary in category_ids if is_primary]
    if len(primaries) > 1:
        raise ServiceError(
            "INVALID_INPUT",
            "a service can have at most one primary category",
            422,
        )
    return primaries[0] if primaries else None


def validate_category_selection(
    category_ids: Sequence[tuple[int, bool]],
    status: ServiceStatus,
) -> None:
    """
    A service may have no categories while it is a draft. Once it is published
    it must have at least one category, and exactly one of them primary, so the
    public page always has a canonical category to show.
    """
    if status not in (ServiceStatus.published,):
        return

    if not category_ids:
        raise ServiceError(
            "INVALID_INPUT",
            "a published service must have at least one category",
            422,
        )

    if resolve_primary_category(category_ids) is None:
        raise ServiceError(
            "INVALID_INPUT",
            "a published service must mark exactly one category as primary",
            422,
        )


def validate_category_assignments(
    requested: Sequence[tuple[int, bool]],
    *,
    active_by_id: dict[int, bool],
    currently_assigned: Optional[set[int]] = None,
    current_primary_id: Optional[int] = None,
    status: ServiceStatus = ServiceStatus.draft,
) -> None:
    """
    Enforce the retired-category ("inactive") rules for a category assignment.

    An inactive category is retired, not deleted: its history is still there and
    a service that already points at it must not silently lose that link just
    because someone deactivated the category. So:

      * an inactive category cannot be *newly* assigned;
      * an already-assigned inactive category may be kept, and may be removed;
      * an inactive category cannot *newly become* the primary one;
      * a published service must have an active primary category.

    `currently_assigned` / `current_primary_id` describe the stored state before
    this save, which is what distinguishes "keeping" from "newly assigning".
    """
    currently_assigned = currently_assigned or set()
    primary_id = resolve_primary_category(requested)

    for category_id, is_primary in requested:
        if category_id not in active_by_id:
            raise ServiceError(
                "CATEGORY_NOT_FOUND",
                f"Unknown category id: {category_id}",
                404,
            )

        active = active_by_id[category_id]
        already_assigned = category_id in currently_assigned

        if not active and not already_assigned:
            raise ServiceError(
                "INVALID_INPUT",
                "an inactive (retired) category cannot be newly assigned to a service",
                422,
            )

        if is_primary and not active and category_id != current_primary_id:
            raise ServiceError(
                "INVALID_INPUT",
                "an inactive (retired) category cannot newly become the primary category",
                422,
            )

    if (
        status == ServiceStatus.published
        and primary_id is not None
        and not active_by_id.get(primary_id, True)
    ):
        raise ServiceError(
            "INVALID_INPUT",
            "a published service must have an active primary category",
            422,
        )


def truncate_to_millis(value: Optional[datetime]) -> Optional[datetime]:
    """
    Drop sub-millisecond precision from a timestamp.

    PostgreSQL keeps microseconds while JavaScript `Date` keeps milliseconds, so
    a value sent by the admin panel can never round-trip exactly. Comparing
    millisecond-truncated values keeps optimistic locking usable from the browser
    without a false conflict on every save.
    """
    if value is None:
        return None
    return value.replace(microsecond=(value.microsecond // 1000) * 1000)


def updated_at_conflicts(
    current: Optional[datetime], expected: Optional[datetime]
) -> bool:
    """
    True when the stored row has moved on since the client loaded it.

    Both sides are truncated to milliseconds first: PostgreSQL stores
    microseconds while a browser `Date` holds only milliseconds, so an exact
    comparison would report a conflict on every save from the admin panel.

    `expected` is None when no token was supplied. The aggregate save requires a
    token, so that only happens for internal callers; it means the caller is not
    asking for conflict detection, and the row lock still serialises writers.
    """
    if expected is None:
        return False
    return truncate_to_millis(current) != truncate_to_millis(expected)


def would_create_category_cycle(
    category_id: int,
    new_parent_id: Optional[int],
    parent_lookup: Callable[[int], Optional[int]],
) -> bool:
    """
    True if setting `new_parent_id` as the parent of `category_id` would create a
    cycle: the proposed parent is the category itself, or one of its descendants.

    Walks upward from the proposed parent through the existing tree using the
    supplied lookup. Guarded against an unrelated pre-existing loop so a corrupt
    tree cannot hang the request.
    """
    if new_parent_id is None:
        return False
    if new_parent_id == category_id:
        return True

    seen = set()
    cursor: Optional[int] = new_parent_id
    while cursor is not None:
        if cursor == category_id:
            return True
        if cursor in seen:
            return False
        seen.add(cursor)
        cursor = parent_lookup(cursor)

    return False
