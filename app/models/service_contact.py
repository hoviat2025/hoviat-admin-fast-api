import enum

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    Text,
    TIMESTAMP,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import Base


class ServiceContactType(str, enum.Enum):
    """
    What kind of value a contact holds. Closed on purpose: the frontend needs to
    know how to render and link each contact, so the set is small and stable.
    The network itself is the free-text `platform`, which is not limited to this
    enum.
    """
    phone = "phone"
    email = "email"
    url = "url"
    username = "username"
    other = "other"


class ServiceContact(Base):
    """
    One contact method for a service: a phone number, an email, a website, a
    social handle, and so on. A service may hold many, of the same type, in a
    chosen order, each independently hideable.

    `platform` is free text so a new social network never needs a migration.
    Icons and other presentation data belong to the frontend, not the database.
    """
    __tablename__ = "service_contacts"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    service_id = Column(
        BigInteger,
        ForeignKey("services.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Human-facing label, e.g. "Main phone", "Reservations", "Instagram".
    title = Column(Text, nullable=False)
    # Machine-readable kind, used to pick the link/prefix rendering.
    type = Column(
        SAEnum(ServiceContactType, name="service_contact_type"), nullable=False
    )
    # The actual contact information.
    value = Column(Text, nullable=False)
    # Optional external network identifier, e.g. "instagram", "telegram".
    platform = Column(Text, nullable=True)

    display_order = Column(Integer, server_default="0", nullable=False)
    is_visible = Column(Boolean, server_default="true", nullable=False)

    created_at = Column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    service = relationship("Service", back_populates="contacts")
