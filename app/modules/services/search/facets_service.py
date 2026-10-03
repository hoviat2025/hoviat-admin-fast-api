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

from app.models.service import Service, ServiceStatus

# Services with no country stated still belong somewhere in the response, or the
# facet count would not add up to the published total. They are grouped under
# this key rather than being silently dropped.
UNSPECIFIED_COUNTRY = None


class ServiceFacetsService:
    def __init__(self, db):
        self.db = db

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