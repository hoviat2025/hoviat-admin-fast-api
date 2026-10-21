"""Canonical location lookup shared by admin and owner writes."""
from sqlalchemy import select
from app.core.exceptions import ServiceError
from app.models.city import City
from app.models.country_state import CountryState
from app.modules.services.location import clean_city, fold


class CityRepository:
    def __init__(self, db):
        self.db = db

    async def resolve(self, country_code, state, city):
        cleaned = clean_city(city)
        if not cleaned:
            return None
        if not country_code:
            raise ServiceError("INVALID_INPUT", "Choose a country before choosing a city", 422)
        stmt = select(City, CountryState).join(CountryState, City.state_id == CountryState.id).where(
            CountryState.country_code == country_code,
            City.is_active.is_(True), CountryState.is_active.is_(True),
        )
        if state:
            stmt = stmt.where(CountryState.name == state)
        rows = (await self.db.execute(stmt)).all()
        matches = [(c, s) for c, s in rows if fold(cleaned) in {fold(c.name), *(fold(a) for a in c.aliases)}]
        if len(matches) != 1:
            message = ("Choose a state to distinguish cities with the same name" if len(matches) > 1
                       else "Choose a defined city from the location catalogue; an admin can add a missing city")
            raise ServiceError("INVALID_INPUT", message, 422)
        return matches[0]

    async def create(self, state_id, name, aliases):
        state = await self.db.get(CountryState, state_id)
        if state is None or not state.is_active:
            raise ServiceError("INVALID_INPUT", "Choose an active state", 422)
        # Serialize catalogue edits so aliases cannot ambiguously overlap.
        from sqlalchemy import text
        await self.db.execute(text("SELECT pg_advisory_xact_lock(606125021)"))
        name = clean_city(name)
        aliases = list(dict.fromkeys(clean_city(a) for a in aliases if clean_city(a)))
        proposed = {fold(name), *(fold(a) for a in aliases)}
        rows = (await self.db.execute(select(City).where(City.state_id == state_id))).scalars().all()
        if any(proposed & {fold(c.name), *(fold(a) for a in c.aliases)} for c in rows):
            raise ServiceError("CONFLICT_OCCURRED", "A city with this name or alias already exists in this state", 409)
        city = City(state_id=state_id, name=name, aliases=aliases)
        self.db.add(city)
        await self.db.flush()
        return city
