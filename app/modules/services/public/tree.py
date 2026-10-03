"""
Public category hierarchy.

Built from ACTIVE categories only. The tree is assembled in Python from a single
flat query rather than by a recursive SQL CTE, because the presentation rule
below is a display decision rather than a filter:

    an active category whose parent is inactive is promoted to a ROOT node.

That is the interesting case. If the parent chain were simply walked and the
orphan dropped, retiring one category would silently delete an entire live
subtree from public navigation - children that are themselves perfectly active
would disappear, and services tagged with them would have no category path to
browse through. Promoting instead keeps the active child reachable, which is
what "retire a category, not its subtree" is supposed to mean.

The whole tree is read in one query. Doing it per-node would be N+1 on a
navigation endpoint, and the hierarchy is small and already in memory anyway.
"""

from typing import Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category
from app.modules.services.public.schemas import PublicCategoryNode

# A category tree guarded against cycles by the domain layer, but this function
# also runs against data that may predate that guard. The cap means a corrupted
# cycle produces a truncated response instead of hanging the request thread.
_MAX_DEPTH = 25


def _build_tree(nodes: List[Category]) -> List[PublicCategoryNode]:
    """
    Assemble parent/child links over already-active `nodes`.

    Split out from the query so the promotion rule can be tested directly against
    hand-built objects, without a database.
    """
    by_id: Dict[int, Category] = {node.id: node for node in nodes}

    children_of: Dict[int, List[Category]] = {}
    roots: List[Category] = []

    for node in nodes:
        # The parent must be present AND active. `by_id` holds active rows only,
        # so a missing parent is exactly the "parent is inactive" case: promote
        # to root rather than dropping the node.
        parent_id = node.parent_id
        if parent_id is not None and parent_id in by_id and parent_id != node.id:
            children_of.setdefault(parent_id, []).append(node)
        else:
            roots.append(node)

    def sort_key(node: Category):
        return (node.display_order, (node.name or "").lower(), node.id)

    def attach(node: Category, depth: int) -> PublicCategoryNode:
        kids = children_of.get(node.id, [])
        kids.sort(key=sort_key)
        return PublicCategoryNode(
            id=node.id,
            name=node.name,
            slug=node.slug,
            display_order=node.display_order,
            parent_id=node.parent_id if node.parent_id in by_id else None,
            children=[
                # Stop recursing at the cap rather than looping forever.
                attach(child, depth + 1)
                if depth + 1 < _MAX_DEPTH
                else []
                for child in kids
            ],
        )

    roots.sort(key=sort_key)
    return [attach(node, 0) for node in roots]


async def build_public_category_tree(session: AsyncSession) -> List[PublicCategoryNode]:
    """
    The public category hierarchy: active categories only.

    Retired categories are excluded at the query, which is what makes an active
    category with a retired parent become a root node - the parent is simply not
    in the result set for the promotion check to find.
    """
    result = await session.execute(
        select(Category)
        .where(Category.is_active.is_(True))
        .order_by(Category.display_order, Category.name)
    )
    return _build_tree(list(result.scalars().all()))