"""
Typed, allow-listed query engine for the service domain.

Deliberately scoped: this is a *service* query layer, not a generic ORM query
framework. It exists because the service domain needs filtering that is
safe to expose publicly, and the legacy `fastapi-filter` user endpoint is not
that thing:

  * it accepts no allow-list per surface, so a field is either filterable
    everywhere or nowhere;
  * it silently ignores unrecognised field names and operators, so a client
    asking for something unsupported gets an unfiltered 200 instead of an error;
  * it cannot express relationship filtering (categories) at all.

Design in one paragraph: a `FieldSpec` declares, per filterable key, which
column it maps to, which operators are permitted, and how to coerce the value.
A `ServiceQueryBuilder` is then constructed with an explicit allow-list of keys
for the calling surface (public vs admin). Any key or operator outside that
allow-list raises `ServiceError` 422 rather than being dropped. Sorting is a
separate allow-list of named modes, not a free column name.

Everything is AND-ed. There is no OR grouping: public discovery does not need
it, and allowing client-supplied boolean structure is exactly the kind of power
that turns into an expensive query.
"""

from dataclasses import dataclass, field as dataclass_field
from enum import Enum
from typing import Any, Callable, Mapping, Optional, Sequence

from sqlalchemy import (
    ColumnElement,
    Integer,
    String,
    Text,
    and_,
    func,
    or_,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql import Select

from app.core.exceptions import ServiceError
from app.models.service import Service, ServiceStatus
from app.models.service_category import ServiceCategory
from app.modules.services.schemas.service_requests import TriStateFilter


class FilterOp(str, Enum):
    """The operator vocabulary. Anything not listed here is rejected."""

    exact = "exact"
    contains = "contains"
    any_of = "any_of"
    none_of = "none_of"
    gt = "gt"
    gte = "gte"
    lt = "lt"
    lte = "lte"
    is_null = "is_null"
    tristate = "tristate"


class SortMode(str, Enum):
    """Named sort modes. Clients pick a name; they never name a column."""

    newest = "newest"
    oldest = "oldest"
    name_asc = "name_asc"
    name_desc = "name_desc"
    recently_updated = "recently_updated"


_SORT_EXPRESSIONS: dict[SortMode, tuple] = {
    SortMode.newest: (Service.created_at.desc(), Service.id.desc()),
    SortMode.oldest: (Service.created_at.asc(), Service.id.asc()),
    SortMode.name_asc: (Service.name.asc(), Service.id.desc()),
    SortMode.name_desc: (Service.name.desc(), Service.id.desc()),
    SortMode.recently_updated: (Service.updated_at.desc(), Service.id.desc()),
}


@dataclass(frozen=True)
class FieldSpec:
    """
    One filterable key.

    `column` is None for keys the engine does not turn into a simple column
    predicate (free-text search, categories); those are handled by dedicated
    builder methods so they cannot be smuggled in through the generic path.
    """

    key: str
    column: Optional[Any]
    ops: frozenset
    coerce: Callable[[str], Any]
    description: str = ""
    #: Structured location keys are compared case-insensitively, which is why
    #: the matching indexes are on lower(...).
    case_insensitive: bool = False


def _as_str(value: Any) -> str:
    return str(value).strip()


def _as_int(value: Any) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        raise ServiceError("INVALID_INPUT", f"{value!r} is not a whole number", 422)


def _as_float(value: Any) -> float:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        raise ServiceError("INVALID_INPUT", f"{value!r} is not a number", 422)


def _as_tristate(value: Any) -> TriStateFilter:
    """
    Coerce a tri-state filter value.

    Accepts the enum names used by the admin API and the shorter yes/no/unknown
    spelling used by the public API, so both surfaces can share one column
    definition without each inventing its own vocabulary.
    """
    raw = str(value).strip().lower()
    mapping = {
        "yes": TriStateFilter.yes,
        "true": TriStateFilter.yes,
        "no": TriStateFilter.no,
        "false": TriStateFilter.no,
        "unknown": TriStateFilter.unknown,
        "null": TriStateFilter.unknown,
        "unset": TriStateFilter.unknown,
    }
    if raw not in mapping:
        raise ServiceError(
            "INVALID_INPUT",
            f"{value!r} is not a valid relevance filter; use yes, no or unknown",
            422,
        )
    return mapping[raw]


_TEXT_OPS = frozenset({FilterOp.exact, FilterOp.contains})
_CMP_OPS = frozenset(
    {FilterOp.exact, FilterOp.gt, FilterOp.gte, FilterOp.lt, FilterOp.lte, FilterOp.is_null}
)
_RELEVANCE_OPS = frozenset({FilterOp.tristate})

def _text(value: Any) -> str:
    return _as_str(value)


def _int(value: Any) -> int:
    return _as_int(value)


def _float(value: Any) -> float:
    return _as_float(value)


def _tristate(value: Any) -> TriStateFilter:
    return _as_tristate(value)


def _bool(value: Any) -> bool:
    """
    Strict boolean parsing for is_null.

    Deliberately does not use Pydantic's bool coercion, which would treat the
    string "false" as True. A filter meant to select rows that DO have a value
    silently selecting the ones that do not would be a nasty, hard-to-spot bug.
    """
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in ("true", "1", "yes"):
        return True
    if text in ("false", "0", "no"):
        return False
    raise ServiceError(
        "INVALID_INPUT", f"{value!r} is not a boolean; use true or false", 422
    )


_EXACT_OPS = frozenset({FilterOp.exact, FilterOp.is_null})
_CITY_OPS = frozenset(
    {FilterOp.exact, FilterOp.contains, FilterOp.is_null}
)
# `is_null` is available on every structured location field so an admin can find
# records whose location was never filled in, which is the same data-quality
# idea as the tri-state relevance columns applied to geography. `any_of` /
# `none_of` allow multi-value country and region filters.
_LOCATION_OPS = frozenset(
    {FilterOp.exact, FilterOp.contains, FilterOp.is_null, FilterOp.any_of, FilterOp.none_of}
)


def _fields() -> dict[str, FieldSpec]:
    """
    The full set of filterable service keys.

    Keys whose column is None are intentionally absent: `q` and categories are
    handled by dedicated builder methods because they need joins or multi-field
    OR semantics, and routing them through the generic path would make them
    look like ordinary columns.
    """
    specs = [
        # ---- location
        FieldSpec("country_code", Service.country_code, _LOCATION_OPS, _text,
                  "ISO-3166-1 alpha-2 country code", case_insensitive=True),
        FieldSpec("state", Service.state, _LOCATION_OPS, _text,
                  "First-level administrative region, canonical spelling", case_insensitive=True),
        # Structured location: `is_null` is available so an admin can find records whose
        # location was never filled in, which is the other half of the tri-state
        # data-quality idea applied to geography.
FieldSpec("city", Service.city, _CITY_OPS, _text,
                  "City name", case_insensitive=True),
        FieldSpec("postal_code", Service.postal_code, _TEXT_OPS, _text,
                  "Postal code, free text", case_insensitive=True),
        FieldSpec("latitude", Service.latitude, _CMP_OPS, _float, "Latitude"),
        FieldSpec("longitude", Service.longitude, _CMP_OPS, _float, "Longitude"),
        # ---- identity / description
        FieldSpec("name", Service.name, _TEXT_OPS, _text, "Service name", case_insensitive=True),
        FieldSpec("description", Service.description, frozenset({FilterOp.contains, FilterOp.is_null}),
                  _text, "Description substring", case_insensitive=True),
        FieldSpec("id", Service.id, _CMP_OPS, _int, "Service id"),
        # ---- classification (tri-state Iranian/Persian relevance)
        FieldSpec("persian_owned", Service.persian_owned, _RELEVANCE_OPS, _tristate),
        FieldSpec("persian_provider", Service.persian_provider, _RELEVANCE_OPS, _tristate),
        FieldSpec("persian_language", Service.persian_language, _RELEVANCE_OPS, _tristate),
        FieldSpec("persian_service", Service.persian_service, _RELEVANCE_OPS, _tristate),
    ]
    return {spec.key: spec for spec in specs}


SERVICE_FILTER_FIELDS: Mapping[str, FieldSpec] = _fields()


def supported_filter_keys() -> list:
    """Public introspection, so a caller can render a filter UI from the truth."""
    return sorted(SERVICE_FILTER_FIELDS)


def supported_sort_modes() -> list:
    return [mode.value for mode in SortMode]


@dataclass
class _Condition:
    field: str
    op: FilterOp
    value: Any
    condition: ColumnElement


@dataclass
class ServiceQueryBuilder:
    """
    Composes a service SELECT.

    Construct with an explicit `allow` set of field keys. A key outside it is
    rejected, which is how one shared engine serves a deliberately small public
    surface and a richer admin surface without either leaking into the other.
    """

    db: AsyncSession
    allow: frozenset
    conditions: list = dataclass_field(default_factory=list)
    order_by: Optional[SortMode] = None
    page: int = 1
    size: int = 20
    #: Whether the caller may constrain `status`. False for public search, which
    #: is what makes a draft unreachable from the public endpoint by construction.
    _allow_status: bool = False
    _include: tuple = ()

    def allow_status(self, enabled: bool = True) -> "ServiceQueryBuilder":
        self._allow_status = enabled
        return self

    # ------------------------------------------------------------ building

    def _spec(self, field: str) -> FieldSpec:
        if field not in SERVICE_FILTER_FIELDS:
            raise ServiceError(
                "INVALID_INPUT",
                f"{field!r} is not a filterable service field",
                422,
            )
        if field not in self.allow:
            raise ServiceError(
                "INVALID_INPUT",
                f"filtering by {field!r} is not supported on this endpoint",
                422,
            )
        return SERVICE_FILTER_FIELDS[field]

    def filter(self, field: str, op: FilterOp | str, value: Any) -> "ServiceQueryBuilder":
        """
        Add one condition.

        Both an unknown field and an unsupported field/operator pair raise, so a
        typo or a capability probe produces a 422 rather than a silently broader
        result set.
        """
        spec = self._spec(field)
        try:
            # Accept an enum member as well as its string value, so callers can
            # pass FilterOp.tristate or "tristate" interchangeably.
            operator = op if isinstance(op, FilterOp) else FilterOp(str(op).lower())
        except ValueError:
            raise ServiceError(
                "INVALID_INPUT",
                f"{op!r} is not a supported operator for {field!r}; "
                f"supported: {', '.join(sorted(o.value for o in spec.ops))}",
                422,
            )
        if operator not in spec.ops:
            raise ServiceError(
                "INVALID_INPUT",
                f"operator {operator.value!r} is not supported for {field!r}; "
                f"supported: {', '.join(sorted(o.value for o in spec.ops))}",
                422,
            )

        coerced = spec.coerce(value)
        self.conditions.append(
            _Condition(
                field=field,
                op=operator,
                value=coerced,
                condition=self._condition_for(spec, operator, coerced),
            )
        )
        return self

    def _condition_for(
        self, spec: FieldSpec, op: FilterOp, value: Any
    ) -> ColumnElement:
        column = spec.column

        if op is FilterOp.tristate:
            if value is TriStateFilter.yes:
                return column.is_(True)
            if value is TriStateFilter.no:
                return column.is_(False)
            # unknown: the value has never been assessed. Deliberately NOT the
            # same as "no", which is the entire reason the column is tri-state.
            return column.is_(None)

        if op is FilterOp.is_null:
            # Parsed here rather than by the field coercer: the field coercer is
            # chosen for the field's natural type (text, int, ...), whereas this
            # operator's value is always a boolean flag. Reusing the field
            # coercer would turn "false" into the truthy string "false".
            return column.is_(None) if _bool(value) else column.is_not(None)

        # Case-insensitive comparison lowers BOTH sides. Lowering only the column
        # would compare lower('DE') against 'DE' and never match, which is
        # exactly the kind of bug that makes a country filter look broken.
        target = func.lower(column) if spec.case_insensitive else column
        compare = value.lower() if (spec.case_insensitive and isinstance(value, str)) else value

        if op is FilterOp.any_of:
            values = [
                item.lower() if (spec.case_insensitive and isinstance(item, str)) else item
                for item in value
            ]
            return func.lower(column).in_(values) if spec.case_insensitive else column.in_(values)
        if op is FilterOp.none_of:
            values = [
                item.lower() if (spec.case_insensitive and isinstance(item, str)) else item
                for item in value
            ]
            return func.lower(column).notin_(values) if spec.case_insensitive else column.notin_(values)

        if op is FilterOp.contains:
            # Escape LIKE metacharacters so a user searching for "50%" or "_x"
            # gets a literal match instead of a wildcard that widens the result.
            escaped = (
                str(compare).replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            )
            return target.like(f"%{escaped}%", escape="\\")

        if op is FilterOp.exact:
            return target == compare
        if op is FilterOp.gt:
            return target > compare
        if op is FilterOp.gte:
            return target >= compare
        if op is FilterOp.lt:
            return target < compare
        if op is FilterOp.lte:
            return target <= compare

        raise ServiceError("INVALID_INPUT", f"unhandled operator {op!r}", 422)

    def text_search(
        self,
        term: Optional[str],
        extra_predicate: Optional[Callable[[str], Any]] = None,
    ) -> "ServiceQueryBuilder":
        """
        Free-text search across the columns that make sense for public discovery.

        Semantics are AND-of-ORs: every word in the term must match, and each
        word may match in ANY of the searched columns. Getting that nesting
        backwards is easy and produces two silent bugs - OR across words would
        match on any single word, and AND across columns would require every
        word to appear in every column, so a service with a null city could never
        match anything.

        `extra_predicate` is a factory taking one already-lowercased word and
        returning a predicate for it. It exists so a caller can widen the
        per-word column set (the service search layer uses it to include
        category name and slug, which needs a correlated subquery). It must be
        per-word, not one predicate for the whole term, or multi-word search
        would silently behave like single-word search.

        Deliberately NOT searched: owner identity, contacts, provenance and
        internal ids. Those are either private, irrelevant to discovery, or
        abuse magnets.
        """
        cleaned = _clean_search_term(term)
        if not cleaned:
            return self

        word_predicates = []
        for raw_word in cleaned.split():
            # Lowercase the WORD, not just the column: comparing lower(col)
            # against the original term would make any term containing an
            # uppercase letter fail to match itself, so q=Kid could never find
            # "Kid".
            word = raw_word.lower()
            pattern = f"%{_escape_like(word)}%"
            matches = [
                func.lower(column).like(pattern, escape="\\")
                for column in (Service.name, Service.description, Service.city, Service.state)
            ]
            if extra_predicate is not None:
                matches.append(extra_predicate(word))
            word_predicates.append(or_(*matches))

        self.conditions.append(
            _Condition(
                field="q",
                op=FilterOp.contains,
                value=cleaned,
                # AND across words, OR within a word.
                condition=and_(*word_predicates),
            )
        )
        return self

    def category_filter(
        self,
        category_ids: Sequence[int],
        *,
        include_descendants: bool = False,
        primary_only: bool = False,
    ) -> "ServiceQueryBuilder":
        """
        Match services assigned to any of `category_ids` (ANY semantics).

        Implemented as EXISTS rather than a JOIN so a service assigned to
        several of the requested categories is returned once, and so the count
        query and the page query cannot disagree.
        """
        from app.modules.services.search.categories import category_scope_condition

        ids = _coerce_id_list(category_ids)
        if not ids:
            return self
        condition = category_scope_condition(
            ids, include_descendants=include_descendants, primary_only=primary_only
        )
        self.conditions.append(
            _Condition(field="category", op=FilterOp.any_of, value=ids, condition=condition)
        )
        return self

    def status(self, status: ServiceStatus) -> "ServiceQueryBuilder":
        """
        Constrain to a status.

        Only the admin surface may name a status; the public surface always
        pins `published` in its allow-list, which is what guarantees a public
        response can never contain a draft.
        """
        if not self._allow_status:
            raise ServiceError(
                "INVALID_INPUT", "filtering by status is not supported here", 422
            )
        self.conditions.append(
            _Condition(field="status", op=FilterOp.exact, value=status,
                       condition=Service.status == status)
        )
        return self

    def published_only(self) -> "ServiceQueryBuilder":
        self.conditions.append(
            _Condition(field="status", op=FilterOp.exact, value=ServiceStatus.published,
                       condition=Service.status == ServiceStatus.published)
        )
        return self

    def sort(self, mode: SortMode | str | None) -> "ServiceQueryBuilder":
        if mode is None:
            return self
        try:
            resolved = SortMode(str(mode).lower())
        except ValueError:
            raise ServiceError(
                "INVALID_INPUT",
                f"{mode!r} is not a supported sort; supported: {', '.join(supported_sort_modes())}",
                422,
            )
        self.order_by = resolved
        return self

    def paginate(self, page: int, size: int, *, max_size: int = 100) -> "ServiceQueryBuilder":
        if page < 1:
            raise ServiceError("INVALID_INPUT", "page must be at least 1", 422)
        if size < 1 or size > max_size:
            raise ServiceError(
                "INVALID_INPUT", f"size must be between 1 and {max_size}", 422
            )
        self.page = page
        self.size = size
        return self

    def eager_load(self) -> "ServiceQueryBuilder":
        """
        Eager-load the relationships the response serializer reads.

        Both must be loaded in the SAME statement that fetches the services.
        Serialization happens after the session's rows have been consumed, so a
        lazy load there would trigger async IO outside the greenlet context and
        raise MissingGreenlet. `category_links.category` is chained so the
        response can include the category name without a second query.
        """
        self._include = (
            selectinload(Service.contacts),
            selectinload(Service.category_links).selectinload(
                ServiceCategory.category
            ),
        )
        return self

    # ----------------------------------------------------------- executing

    def raw_condition(self, field: str, column: Any, op: str, value: Any) -> "ServiceQueryBuilder":
        """
        Escape hatch for an admin-only predicate on a field the public surface
        must never expose (provenance, owner).

        It is named `raw_condition` rather than hidden, and it still goes through
        the same operator/coercion machinery, so a caller cannot pass an
        arbitrary column *name* from a request: the column object is supplied by
        code, and only the value comes from the request. What the public surface
        can reach is still governed entirely by `allow`.
        """
        coerce = _text if isinstance(column.type, (Text, String)) else (
            _int if isinstance(column.type, Integer) else (lambda v: v)
        )
        spec = FieldSpec(
            key=field,
            column=column,
            ops=frozenset({FilterOp.exact}),
            coerce=coerce,
        )
        operator = FilterOp(op)
        coerced = spec.coerce(value)
        self.conditions.append(
            _Condition(field=field, op=operator, value=coerced,
                       condition=self._condition_for(spec, operator, coerced))
        )
        return self

    def _stmt(self) -> Select:
        stmt = select(Service)
        for condition in self.conditions:
            stmt = stmt.where(condition.condition)
        expressions = _SORT_EXPRESSIONS.get(
            self.order_by or SortMode.newest, _SORT_EXPRESSIONS[SortMode.newest]
        )
        # Every sort mode carries a unique tiebreaker, so paging is stable: two
        # services with the same name or timestamp cannot swap places between
        # page 1 and page 2.
        for expression in expressions:
            stmt = stmt.order_by(expression)
        return stmt

    async def count(self) -> int:
        # Drop ORDER BY before counting: it is irrelevant to the count and can
        # otherwise force a sort of the whole result set.
        stmt = select(Service)
        for condition in self.conditions:
            stmt = stmt.where(condition.condition)
        total = await self.db.scalar(select(func.count()).select_from(stmt.subquery()))
        return int(total or 0)

    async def all(self) -> Sequence[Service]:
        stmt = self._stmt().offset((self.page - 1) * self.size).limit(self.size)
        if self._include:
            stmt = stmt.options(*self._include)
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def execute(self) -> tuple:
        """Return (rows, total) for one page."""
        return await self.all(), await self.count()


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


_MAX_SEARCH_WORDS = 8
_MAX_SEARCH_TERM_LENGTH = 100


def _clean_search_term(term: Optional[str]) -> Optional[str]:
    """
    Bound a free-text term before it reaches the database.

    Caps length and word count. A 10 KB search string is not a search, and
    unbounded ILIKE terms are a cheap way to make an index-less scan expensive.
    """
    if term is None:
        return None
    cleaned = " ".join(str(term).split())
    if not cleaned:
        return None
    if len(cleaned) > _MAX_SEARCH_TERM_LENGTH:
        cleaned = cleaned[:_MAX_SEARCH_TERM_LENGTH]
    words = cleaned.split()
    if len(words) > _MAX_SEARCH_WORDS:
        cleaned = " ".join(words[:_MAX_SEARCH_WORDS])
    return cleaned


def _coerce_id_list(values: Any) -> list:
    if values is None:
        return []
    if isinstance(values, (str, int)):
        values = [values]
    out = []
    for value in values:
        text = str(value).strip()
        if not text:
            continue
        try:
            out.append(int(text))
        except ValueError:
            raise ServiceError(
                "INVALID_INPUT", f"{value!r} is not a valid category id", 422
            )
    # De-duplicate so a repeated id cannot widen or distort the IN list.
    return sorted(set(out))