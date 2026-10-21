"""Shared city catalogue. Services reference these rows, never invent cities."""
from sqlalchemy import ARRAY, BigInteger, Boolean, Column, ForeignKey, Index, Text, TIMESTAMP
from sqlalchemy.sql import func
from app.models.base import Base
from app.models.country_state import CountryState  # noqa: F401


class City(Base):
    __tablename__ = "cities"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    state_id = Column(BigInteger, ForeignKey("country_states.id", ondelete="RESTRICT"), nullable=False)
    name = Column(Text, nullable=False)
    aliases = Column(ARRAY(Text), nullable=False, server_default="{}")
    is_active = Column(Boolean, nullable=False, server_default="true")
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    __table_args__ = (Index("cities_state_name_key", state_id, func.lower(name), unique=True),)
