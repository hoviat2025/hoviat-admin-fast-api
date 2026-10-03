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


def descendant_category_cte(category_ids: Sequence[int], alias: str = "scoped_category"):
    """
    A recursive CTE yielding `category_ids` plus all of their descendants.

    `UNION ALL` is safe here: the categories table is a tree guarded against
    cycles by the domain layer, and a duplicate row would only mean the same
    category id is processed twice, not an infinite walk. `UNION` would be
    marginally safer at the cost of a dedupe step; the category tree is
    acyclic by construction, so the cheaper form is used deliberately.
    """
    anchor = (
        select(Category.id.label("id"))
        .where(Category.id.in_(list(category_ids)))
        .cte(alias, recursive=True)
    )
    return anchor.union_all(
        select(Category.id.label("id")).where(Category.parent_id == anchor.c.id)
    )


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
):
    """
    Condition matching services assigned to any of `category_ids`.

    `include_descendants` expands each id to its subtree via the recursive CTE,
    so selecting a parent matches services tagged anywhere below it.

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
        scope = descendant_category_cte(ids)
        matcher = ServiceCategory.category_id.in_(select(scope.c.id))
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
        select(ServiceCategory.id)
        .join(Category, Category.id == ServiceCategory.category_id)
        .where(ServiceCategory.service_id == Service.id)
    )