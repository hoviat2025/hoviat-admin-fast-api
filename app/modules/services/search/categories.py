"""
Category scope resolution for service search.

Two concerns:

  * "does this category have ancestors" — when a user clicks a parent like
    "Restaurants", should services tagged with its child "Iranian restaurants"
    appear? Public discovery says yes, so selecting a category matches the whole
    subtree.

  * the matching itself, as EXISTS against the service_categories link.

The subtree is resolved with a PostgreSQL recursive CTE rather than by walking
the tree in Python. Doing it in the database keeps the query a single round trip
regardless of depth, and it cannot drift from the actual tree the way a
cached in-memory copy would.
"""

from typing import Sequence

from sqlalchemy import exists, select
from sqlalchemy.sql import Select

from app.models.category import Category
from app.models.service import Service
from app.models.service_category import ServiceCategory


def descendant_category_cte(category_ids: Sequence[int], alias: str = "scoped_category", active_only: bool = False):
    """
    A recursive CTE yielding `category_ids` plus all of their descendants.

    `UNION ALL` is safe here: the categories table is a tree guarded against
    cycles by the domain layer, and a duplicate row would only mean the same
    category id is processed twice, not an infinite walk. `UNION` would be
    marginally safer at the cost of a dedupe step; the category tree is
    acyclic by construction, so the cheaper form is used deliberately.

    `active_only` restricts expansion to ACTIVE categories. Used by public
    discovery: a retired category in the middle of the tree must not keep
    widening the match set, otherwise a retired branch would keep returning
    services through its descendants.
    """
    anchor_stmt = select(Category.id.label("id")).where(Category.id.in_(list(category_ids)))
    if active_only:
        anchor_stmt = anchor_stmt.where(Category.is_active.is_(True))
    anchor = anchor_stmt.cte(alias, recursive=True)

    child_stmt = select(Category.id.label("id")).where(Category.parent_id == anchor.c.id)
    if active_only:
        child_stmt = child_stmt.where(Category.is_active.is_(True))
    return anchor.union_all(child_stmt)


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

    `include_descendants` expands each id to its subtree via the recursive CTE,
    so selecting a parent matches services tagged anywhere below it.

    `primary_only` restricts to the service's primary category, which is a
    genuinely different question: "primary category is Restaurants" is narrower
    than "is tagged Restaurants somewhere". Without the flag, both primary and
    secondary assignments match, which is the right default for discovery.

    `active_only` is the public-discovery rule: a retired category must not make
    a service match, and must not be reachable by descending through it. Admin
    search leaves this False so admins keep full visibility of historical
    assignments, including retired ones.

    Exists, not join: a service carrying several of the requested categories
    must still be returned once, and the page query and the count query must
    agree. A join would multiply rows and make both wrong.
    """
    ids = list(category_ids)
    if include_descendants:
        scope = descendant_category_cte(ids, active_only=active_only)
        matcher = ServiceCategory.category_id.in_(select(scope.c.id))
    else:
        matcher = ServiceCategory.category_id.in_(ids)
        if active_only:
            matcher = ServiceCategory.category_id.in_(
                select(Category.id).where(
                    Category.id.in_(ids), Category.is_active.is_(True)
                )
            )

    link_filter = [ServiceCategory.service_id == Service.id, matcher]
    if primary_only:
        link_filter.append(ServiceCategory.is_primary.is_(True))

    # ServiceCategory's primary key is the composite (service_id, category_id),
    # so it has no single-column `id` to select. Selecting category_id is both
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

    Note: the live `q` path uses `_category_text_search` in the search service,
    not this helper, because that is a per-word predicate factory (see
    `ServiceQueryBuilder.text_search`). This helper takes no `active_only` flag
    for that reason; adding one here would be an unused parameter on a function
    nothing calls.
    """
    return (
        select(ServiceCategory.id)
        .join(Category, Category.id == ServiceCategory.category_id)
        .where(ServiceCategory.service_id == Service.id)
    )