"""
Location facets derived from the services that are actually published.

The endpoint answers "where can I browse?" rather than "what locations exist?".
A country or city with no published services is omitted entirely, which keeps
the response honest and stops the frontend offering filters that return nothing.

The shape is deliberately international: countries are the top level, so the
Germany-first frontend renders the DE branch and another country appears with no
change here.
"""

from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.models.service import Service, ServiceStatus
from app.models.category import Category
from app.models.service_category import ServiceCategory
from app.models.city import City
from app.models.country_state import CountryState
from app.modules.services.schemas.public_service_responses import PublicCategoryTreeResponse

# Services with no country stated still belong somewhere in the response, or the
# facet count would not add up to the published total. They are grouped under
# this key rather than being silently dropped.
UNSPECIFIED_COUNTRY = None


class ServiceFacetsService:
    def __init__(self, db):
        self.db = db

    async def location_catalogue(self) -> list:
        """Defined locations for editors, including cities without listings."""
        counts = dict((await self.db.execute(
            select(Service.city_id, func.count(Service.id))
            .where(Service.status == ServiceStatus.published, Service.city_id.is_not(None))
            .group_by(Service.city_id)
        )).all())
        rows = (await self.db.execute(
            select(CountryState, City).outerjoin(City, (City.state_id == CountryState.id) & City.is_active.is_(True))
            .where(CountryState.is_active.is_(True)).order_by(CountryState.country_code, CountryState.name, City.name)
        )).all()
        countries, states = {}, {}
        for state, city in rows:
            country = countries.setdefault(state.country_code, {"country_code": state.country_code, "total": 0, "states": []})
            if state.id not in states:
                states[state.id] = {"id": state.id, "state": state.name, "total": 0, "cities": []}
                country["states"].append(states[state.id])
            if city:
                count = counts.get(city.id, 0)
                states[state.id]["cities"].append({"id": city.id, "city": city.name, "count": count})
                states[state.id]["total"] += count
                country["total"] += count
        return list(countries.values())

    async def category_tree(self, country_code: str | None = None) -> list:
        """All active taxonomy choices, including branches with no listings.

        The vocabulary is shared across countries. country_code is accepted for
        API compatibility; it does not fabricate listings or category counts.
        """
        rows = (
            await self.db.execute(
                select(Category)
                .where(Category.is_active.is_(True))
                .options(selectinload(Category.parent_links))
                .execution_options(populate_existing=True)
                .order_by(Category.display_order, Category.name, Category.id)
            )
        ).scalars().all()
        return _category_tree(rows)

    async def location_facets(self) -> list:
        """
        country -> regions -> cities, each with a published-service count.

        One grouped query over the published set, then assembled in Python.
        Doing the grouping in SQL would need a recursive type or repeated
        round trips for a hierarchy that is small by construction: only the
        locations that exist, which is bounded by the data.

        Counts are of published services, not of rows in the locations
        themselves, so a city count answers "how many published services are
        here".
        """
        rows = (
            await self.db.execute(
                select(
                    Service.country_code,
                    Service.state,
                    Service.city,
                    func.count(Service.id),
                )
                .where(Service.status == ServiceStatus.published)
                .where(
                    (Service.city.is_not(None))
                    | (Service.state.is_not(None))
                    | (Service.country_code.is_not(None))
                )
                .group_by(Service.country_code, Service.state, Service.city)
            )
        ).all()

        countries: dict = {}

        for country_code, state, city, count in rows:
            country = countries.setdefault(
                country_code, {"country_code": country_code, "total": 0, "states": {}}
            )
            country["total"] += count

            state_key = state
            state_entry = country["states"].setdefault(
                state_key,
                {
                    "state": state,
                    "total": 0,
                    "cities": {},
                },
            )
            state_entry["total"] += count

            if city:
                city_entry = state_entry["cities"].setdefault(
                    city, {"city": city, "count": 0}
                )
                city_entry["count"] += count

        return [_finalise_country(country) for country in countries.values()]


def _category_tree(rows) -> list[PublicCategoryTreeResponse]:
    roots = {
        row.id: PublicCategoryTreeResponse(id=row.id, name=row.name, slug=row.slug, level=1)
        for row in rows if row.parent_id is None
    }
    for row in rows:
        if row.parent_id is None:
            continue
        parent_ids = getattr(row, "parent_ids", None) or [row.parent_id]
        for parent_id in parent_ids:
            if parent_id in roots:
                roots[parent_id].children.append(PublicCategoryTreeResponse(
                    id=row.id, name=row.name, slug=row.slug,
                    parent_id=row.parent_id, parent_ids=list(parent_ids), level=2,
                ))
    return list(roots.values())


def _finalise_country(country: dict) -> dict:
    states = []
    for state in country["states"].values():
        cities = sorted(state["cities"].values(), key=lambda item: item["city"])
        states.append(
            {
                "state": state["state"],
                "total": state["total"],
                "cities": cities,
            }
        )
    states.sort(key=lambda item: (item["state"] is None, item["state"] or ""))
    return {
        "country_code": country["country_code"],
        "total": country["total"],
        "states": states,
    }
