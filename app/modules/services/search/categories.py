"""
Category scope resolution for service search.

Two concerns:

  * "does this category have ancestors" — when a user clicks a parent like
    "Restaurants", should services tagged with its child "Iranian restaurants"
    appear? Public discovery says yes, so selecting a category matches the whole
    subtree.

  * the matching itself, as EXISTS against the service_categories link.

Membership expansion stays in the query: a selected root matches children
linked through any root membership, and EXISTS avoids duplicate service rows.
"""

from typing import Sequence

from sqlalchemy import exists, select
from sqlalchemy.sql import Select

from app.models.category import Category, CategoryParent
from app.models.service import Service
from app.models.service_category import ServiceCategory


def descendant_category_cte(
    category_ids: Sequence[int], alias: str = "scoped_category", active_only: bool = False
):
    """
    Selected category ids plus their level-two root memberships, without duplicates.
    """
    # Exactly two levels: selected categories plus children linked to ANY
    # selected root. UNION deduplicates a shared child reached from two roots.
    ids = list(category_ids)
    selected = select(Category.id.label("id")).where(Category.id.in_(ids)).correlate(None)
    if active_only:
        selected = selected.where(Category.is_active.is_(True))
    # Limit both ends of a public membership to active categories: selecting a
    # retired root must not expose services under its still-active children.
    children = select(CategoryParent.category_id.label("id")).where(
        CategoryParent.parent_id.in_(selected)
    )
    if active_only:
        children = children.join(Category, Category.id == CategoryParent.category_id).where(
            Category.is_active.is_(True)
        )
    return selected.union(children).cte(alias)


async def resolve_descendants(db, category_ids: Sequence[int]) -> list:
    """
    Materialise the expanded id set. Used where an id list is needed directly,
    such as building a location facet or reporting what a filter resolved to.
    """
    cte = descendant_category_cte(category_ids)
    result = await db.execute(select(cte.c.id))
    return sorted({row[0] for row in result.all()})


def category_scope_condition(
    category_ids: Sequence[int],
    *,
    include_descendants: bool = True,
    primary_only: bool = False,
    active_only: bool = False,
):
    """
    Condition matching services assigned to any of `category_ids`.

    `include_descendants` includes children linked through any root membership.
    `active_only` excludes retired categories on the public surface; admin
    callers retain the default unrestricted scope.

    `primary_only` restricts to the service's primary category, which is a
    genuinely different question: "primary category is Restaurants" is narrower
    than "is tagged Restaurants somewhere". Without the flag, both primary and
    secondary assignments match, which is the right default for discovery.

    Exists, not join: a service carrying several of the requested categories
    must still be returned once, and the page query and the count query have to
    agree. A join would multiply rows and make both wrong.
    """
    ids = list(category_ids)
    if include_descendants:
        scope = descendant_category_cte(ids, active_only=active_only)
        matcher = ServiceCategory.category_id.in_(select(scope.c.id))
    elif active_only:
        matcher = ServiceCategory.category_id.in_(
            select(Category.id).where(Category.id.in_(ids), Category.is_active.is_(True))
        )
    else:
        matcher = ServiceCategory.category_id.in_(ids)

    link_filter = [ServiceCategory.service_id == Service.id, matcher]
    if primary_only:
        link_filter.append(ServiceCategory.is_primary.is_(True))

    # ServiceCategory's primary key is the composite (service_id, category_id),
    # so there is no single-column `id` to select. Selecting category_id is both
    # correct and cheaper.
    return exists(select(ServiceCategory.category_id).where(*link_filter))


def category_text_columns() -> Sequence:
    """
    Category columns that participate in free-text search.

    Name and slug only. Category description is editorial copy and would add
    noise to a user-facing search box.
    """
    return (Category.name, Category.slug)


def category_text_exists() -> Select:
    """
    EXISTS subquery linking a service to a category whose name or slug matches.

    Used to fold category text into `q` without joining, for the same
    de-duplication reason as above.
    """
    return (
        select(ServiceCategory.category_id)
        .join(Category, Category.id == ServiceCategory.category_id)
        .where(ServiceCategory.service_id == Service.id)
    )
