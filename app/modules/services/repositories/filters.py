"""
Shared query fragments for the service filters.

Kept separate from app/modules/services/validation.py on purpose: that module is
pure business-rule logic with no database concerns so it can be unit-tested in
isolation, whereas these helpers build SQLAlchemy expressions for the listing
queries.
"""

from typing import Any, Optional

from sqlalchemy import ColumnElement

from app.modules.services.schemas.service_requests import TriStateFilter


def relevance_condition(
    column: Any, filter_value: Optional[TriStateFilter]
) -> Optional[ColumnElement[bool]]:
    """
    Turn a tri-state filter into a column condition.

    The point of a tri-state column is that "not assessed" is a third answer, so
    the filter must be able to select it. An optional boolean filter cannot do
    this: `false` and "no filter" would be indistinguishable.
    """
    if filter_value is None:
        return None
    if filter_value is TriStateFilter.yes:
        return column.is_(True)
    if filter_value is TriStateFilter.no:
        return column.is_(False)
    # unknown / not assessed
    return column.is_(None)