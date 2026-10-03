from sqlalchemy import (
    ARRAY,
    BigInteger,
    Boolean,
    Column,
    Index,
    Text,
    TIMESTAMP,
)
from sqlalchemy.sql import func

from app.models.base import Base


class CountryState(Base):
    """
    Canonical first-level administrative region names, scoped per country.

    For DE these are the 16 Bundeslaender; for CH they would be cantons, for CA
    provinces, and so on. Only Germany is populated today, and that is data, not
    schema: another country is an INSERT.

    The table exists to stop `services.state` fragmenting into spelling variants.
    Two rows for Germany ("Hesse" and "Hessen") would silently split one
    administrative region into two filters, and one of them would always look
    empty. Storing one canonical value per country keeps structured filtering
    meaningful without imposing a closed list on countries we know nothing about.

    When a country has no rows here, its `services.state` values are stored as
    free text. Normalisation code paths are therefore written to degrade to
    pass-through rather than to reject.
    """

    __tablename__ = "country_states"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    country_code = Column(Text, nullable=False)
    name = Column(Text, nullable=False)
    slug = Column(Text, nullable=False)
    # Alternative spellings that must resolve to this canonical name: English
    # names, abbreviations, and ASCII-folded umlaut forms.
    aliases = Column(ARRAY(Text), nullable=False, server_default="{}")
    is_active = Column(Boolean, server_default="true", nullable=False)

    created_at = Column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("country_states_country_name_key", country_code, func.lower(name), unique=True),
        Index("country_states_slug_key", func.lower(slug), unique=True),
    )