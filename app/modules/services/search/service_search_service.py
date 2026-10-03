"""
Service search: the shared query layer, plus the public and admin facades.

Three pieces, kept separate on purpose:

  * `query.py`      — the engine: allow-listed fields, operators, sorting, paging.
  * `service_search_service.py` — compiles a validated params object into an
    engine query for one of the two surfaces.
  * `categories.py` — the recursive category-scope CTE.

The two surfaces (public and admin) deliberately have different contracts. The
public one is a small, obvious vocabulary a person can type into a URL bar; the
admin one is richer. They share the engine, so the admin capability cannot drift
away from what the public surface can express, and the public surface cannot
accidentally inherit an admin-only filter.
"""

from functools import partial

from sqlalchemy import exists, select

from app.core.exceptions import ServiceError
from app.models.service import Service as ServiceColumns
from app.modules.services.public.projection import (
    to_public_detail,
    to_public_summary,
)
from app.modules.services.schemas.service_requests import (
    AdminServiceSearchParams,
    PublicServiceSearchParams,
)
from app.modules.services.schemas.service_responses import ServiceResponse
from app.modules.services.search.query import FilterOp, ServiceQueryBuilder

# The public surface's allow-list. Exactly the keys the public schema declares,
# listed again here on purpose: the allow-list is the security boundary, and it
# is far better for it to be redundant with the schema than to be derived from it
# and therefore change silently when the schema grows.
PUBLIC_ALLOW = frozenset(
    {
        "country_code",
        "state",
        "city",
        "persian_owned",
        "persian_provider",
        "persian_language",
        "persian_service",
    }
)

# Admin additionally gets the scalar fields a moderator needs.
ADMIN_ALLOW = PUBLIC_ALLOW | frozenset(
    {"postal_code", "name", "description", "id", "latitude", "longitude"}
)

_RELEVANCE_KEYS = (
    "persian_owned",
    "persian_provider",
    "persian_language",
    "persian_service",
)


class ServiceSearchService:
    def __init__(self, db):
        self.db = db
        # Two separate serializers on purpose. The admin path must keep using the
        # full record (provenance, owner ids, hidden contacts and retired
        # categories are legitimate admin capabilities). The public path uses the
        # projection in app.modules.services.public, which cannot emit those.
        self._serialize_admin = partial(ServiceService._to_response)

    async def public_search(
        self, params: PublicServiceSearchParams
    ) -> tuple:
        """
        Public discovery search.

        Always published-only. That is applied by the builder, not by trusting the
        caller: there is no `status` parameter on the public schema and the
        builder refuses a status filter unless explicitly permitted, so a client
        cannot ask for drafts even by accident.

        The endpoint does NOT pin a country. The Germany-first frontend passes
        `country_code=DE`; a caller interested in Austria passes `AT`. Not
        defaulting here is deliberate: silently returning Germany when no country
        was asked for would hide a product rule inside the backend.

        Retired categories are excluded from matching (`active_only=True`) and
        from the projected response, so a category that an admin has retired
        stops driving public discovery without any admin having to edit the
        service.
        """
        builder = ServiceQueryBuilder(self.db, allow=PUBLIC_ALLOW).published_only()

        if params.q:
            builder.text_search(
                params.q, extra_predicate=partial(_category_text_search, active_only=True)
            )
        if params.country_code:
            builder.filter("country_code", FilterOp.exact, params.country_code)
        if params.state:
            builder.filter("state", FilterOp.exact, params.state)
        if params.city:
            builder.filter("city", FilterOp.exact, params.city)
        for key in _RELEVANCE_KEYS:
            value = getattr(params, key, None)
            if value is not None:
                builder.filter(key, FilterOp.tristate, value.value)
        if params.category:
            # ANY semantics, and a parent id matches services tagged with any of
            # its descendants. Active-only: a retired category must not match.
            builder.category_filter(
                params.category, include_descendants=True, active_only=True
            )

        builder.sort(params.sort).paginate(params.page, params.size).eager_load()

        rows, total = await builder.execute()
        return [to_public_summary(row) for row in rows], total

    async def public_detail(self, service_id: int):
        """
        Fetch one published service for the public detail page.

        Returns None for anything that is not publicly available: a draft,
        hidden or archived record, or an id that does not exist. The caller maps
        that to 404, so a non-published record is indistinguishable from a
        missing one and its existence is not disclosed.
        """
        builder = (
            ServiceQueryBuilder(self.db, allow=PUBLIC_ALLOW)
            .published_only()
            # `raw_condition`, not `filter("id", ...)`: "id" is deliberately not in
            # PUBLIC_ALLOW, because it is not a search facet a caller should be
            # able to sweep. Detail looks a record up by its own path parameter
            # instead, which is the escape hatch's documented purpose. published_only()
            # above is what keeps this from becoming a way to read a draft.
            .raw_condition("id", ServiceColumns.id, "exact", service_id)
            .eager_load()
            .with_owner_privacy()
        )
        rows, _ = await builder.execute()
        if not rows:
            return None

        service = rows[0]
        return to_public_detail(service, privacy=_owner_privacy(service))

    async def admin_search(self, params: AdminServiceSearchParams) -> tuple:
        """
        Admin listing search.

        Richer than the public surface and intentionally a different contract.
        Status is filterable here, so an admin can list drafts; owner,
        provenance and exact-name lookups are also available.
        """
        builder = ServiceQueryBuilder(self.db, allow=ADMIN_ALLOW).allow_status()

        if params.status is not None:
            builder.status(params.status)
        if params.q:
            builder.text_search(params.q, extra_predicate=_category_text_search)
        if params.country_code:
            builder.filter("country_code", FilterOp.exact, params.country_code)
        if params.state:
            builder.filter("state", FilterOp.exact, params.state)
        if params.city:
            builder.filter("city", FilterOp.exact, params.city)
        if params.postal_code:
            builder.filter("postal_code", FilterOp.exact, params.postal_code)
        if params.name:
            builder.filter("name", FilterOp.exact, params.name)
        for key in _RELEVANCE_KEYS:
            value = getattr(params, key, None)
            if value is not None:
                builder.filter(key, FilterOp.tristate, value.value)

        category_ids = list(params.category_ids or [])
        if params.category_id is not None:
            category_ids.append(params.category_id)
        if category_ids:
            builder.category_filter(
                category_ids,
                include_descendants=True,
                primary_only=params.category_primary_only,
            )

        # Provenance, owner and external id are admin-only concerns, so they are
        # not in the shared allow-list. They go through raw_condition, where the
        # column is supplied by this code and only the value comes from the
        # request, so a client can never name a column.
        if params.source is not None:
            builder.raw_condition("source", ServiceColumns.source, "exact", params.source)
        if params.external_id is not None:
            builder.raw_condition(
                "external_id", ServiceColumns.external_id, "exact", params.external_id
            )
        if params.owner_user_id is not None:
            builder.raw_condition(
                "owner_user_id",
                ServiceColumns.owner_user_id,
                "exact",
                _coerce_owner_id(params.owner_user_id),
            )

        builder.sort(params.sort).paginate(params.page, params.size).eager_load()

        rows, total = await builder.execute()
        return [self._serialize_admin(None, row) for row in rows], total


def _owner_privacy(service):
    """
    The owning user's `UserPrivacySettings`, or None if they have no row.

    The owner relation is eager-loaded, but the owner's privacy row is a
    separate relation, so it is reached through the loaded user rather than being
    issued as a separate query per row. A missing privacy row means "no public
    display", which is the same answer the SNS profile search gives for a user
    with no settings row.
    """
    owner = service.owner
    if owner is None:
        return None
    return getattr(owner, "privacy_settings", None)


def _escape_like(value: str) -> str:
    """Escape LIKE metacharacters so a user's `%` or `_` is matched literally."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _category_text_search(word: str, active_only: bool = False):
    """
    Predicate factory: does this service have a category whose name or slug
    contains `word`?

    Called once per search word by the shared `q` builder, so a multi-word search
    requires every word to match somewhere. That is why this is a factory rather
    than a single predicate built for the whole term.

    `word` arrives already lowercased by the engine, matching the column lowering
    applied here. LIKE metacharacters are escaped, so `q=%` cannot match every
    service.

    EXISTS rather than a JOIN: a service tagged with two matching categories
    must still be returned once, and the page query and the count query must
    agree.

    `active_only` keeps retired categories out of public discovery matches. The
    predicate is still called once per search word, so `active_only` must be
    bound as a keyword argument (via `partial`) rather than being a positional
    parameter that would be mistaken for `word`.
    """
    from app.models.category import Category
    from app.models.service_category import ServiceCategory

    pattern = f"%{_escape_like(word)}%"

    conditions = [
        ServiceCategory.service_id == ServiceColumns.id,
        (
            (func.lower(Category.name).like(pattern, escape="\\"))
            | (func.lower(Category.slug).like(pattern, escape="\\"))
        ),
    ]
    if active_only:
        conditions.append(Category.is_active.is_(True))

    # ServiceCategory's primary key is the composite (service_id, category_id),
    # so it has no single-column `id` to select. Selecting the category id is
    # both correct and cheaper.
    return exists(
        select(ServiceCategory.category_id)
        .join(Category, Category.id == ServiceCategory.category_id)
        .where(*conditions)
    )


def _coerce_owner_id(value) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        raise ServiceError("INVALID_INPUT", "owner_user_id must be an integer", 422)


from sqlalchemy import func  # noqa: E402
from app.modules.services.services.service_service import ServiceService  # noqa: E402