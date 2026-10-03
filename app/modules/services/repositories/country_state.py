"""Access to the country-scoped first-level region vocabulary."""

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.country_state import CountryState
from app.modules.services.location import StateVocabulary


class CountryStateRepository:
    """
    Reads `country_states` and hands back an immutable `StateVocabulary`.

    Caching is the caller's business: this stays a plain repository with no
    hidden state, so a long-lived instance cannot serve a stale vocabulary.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def vocabulary(self, country_code: Optional[str]) -> Optional[StateVocabulary]:
        """
        Vocabulary for a country, or None when that country has no rows.

        Returning None is the normal, expected answer for every country except
        DE, and it is what tells the normalisation layer to pass the value
        through instead of validating it.
        """
        if not country_code:
            return None
        rows = (
            await self.db.execute(
                select(CountryState.name, CountryState.aliases).where(
                    CountryState.country_code == country_code,
                    CountryState.is_active.is_(True),
                )
            )
        ).all()
        if not rows:
            return None
        return StateVocabulary.from_rows(
            country_code, [row.name for row in rows], [row.aliases for row in rows]
        )

    async def names(self, country_code: str) -> list:
        """Canonical names for a country, for driving a suggestions list."""
        result = await self.db.execute(
            select(CountryState.name)
            .where(
                CountryState.country_code == country_code,
                CountryState.is_active.is_(True),
            )
            .order_by(CountryState.name)
        )
        return [row[0] for row in result.all()]

    async def populated_countries(self) -> list:
        """Every country that currently has a vocabulary, for admin tooling."""
        result = await self.db.execute(
            select(CountryState.country_code)
            .distinct()
            .order_by(CountryState.country_code)
        )
        return [row[0] for row in result.all()]