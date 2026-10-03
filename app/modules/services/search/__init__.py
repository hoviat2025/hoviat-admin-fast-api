"""
Service search: the shared query layer, plus the public and admin facades.

Three pieces, kept separate on purpose:

  * `query.py`      — the engine: allow-listed fields, operators, sorting, paging.
  * `service_search_service.py` — compiles a validated params object into an
    engine query for one of the two surfaces.
  * `categories.py` — the recursive category-scope CTE.

The two surfaces (public and admin) deliberately have different contracts. The
public one is a small, obvious vocabulary a person can type into a URL bar; the
admin one is richer. They share the engine, so the admin capability cannot
drift away from what the public surface can express, and the public surface
cannot accidentally inherit an admin-only filter.
"""

from app.modules.services.search.categories import (
    category_scope_condition,
    descendant_category_cte,
    resolve_descendants,
)
from app.modules.services.search.query import (
    SERVICE_FILTER_FIELDS,
    FilterOp,
    ServiceQueryBuilder,
    SortMode,
    supported_filter_keys,
    supported_sort_modes,
)

__all__ = [
    "SERVICE_FILTER_FIELDS",
    "FilterOp",
    "ServiceQueryBuilder",
    "SortMode",
    "category_scope_condition",
    "descendant_category_cte",
    "resolve_descendants",
    "supported_filter_keys",
    "supported_sort_modes",
]