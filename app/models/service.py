import enum

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Double,
    Enum as SAEnum,
    ForeignKey,
    Text,
    TIMESTAMP,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import Base

# Import related models so they are registered in Base.metadata before the ORM
# mapper initializes, mirroring app/models/user.py.
from app.models.user import User  # noqa: F401
from app.models.category import Category  # noqa: F401
from app.models.service_category import ServiceCategory
from app.models.service_contact import ServiceContact


class ServiceStatus(str, enum.Enum):
    """
    Admin-controlled publishing state.

    draft      not publicly visible, still being prepared
    published  publicly visible and discoverable
    hidden     deliberately removed from public discovery without deleting data
    archived   inactive/old record, kept for history
    """
    draft = "draft"
    published = "published"
    hidden = "hidden"
    archived = "archived"


class Service(Base):
    """
    A service / business directory listing.

    Independent of the user entity: owner_user_id is optional, and the listing
    survives the owner being deleted (ON DELETE SET NULL). Ownership is not an
    authorization concept — editing permissions live elsewhere (admins now,
    owner self-management later).
    """
    __tablename__ = "services"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    # Optional owner. A service may have no associated user at all.
    owner_user_id = Column(
        BigInteger,
        ForeignKey("users_eurobot.user_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Whether the owner relationship may be shown publicly. Defaults to false:
    # attaching an owner must never by itself expose that relationship publicly.
    # Public display also requires the owner's own privacy settings to permit
    # it; that check belongs to the read layer, not here.
    show_owner = Column(Boolean, server_default="false", nullable=False)

    name = Column(Text, nullable=False)
    description = Column(Text, nullable=True)

    # Three independent Persian/Iranian relevance signals.
    persian_owned = Column(Boolean, server_default="false", nullable=False)
    persian_language = Column(Boolean, server_default="false", nullable=False)
    persian_service = Column(Boolean, server_default="false", nullable=False)

    # Structured location (searchable), deliberately not a contact row.
    address = Column(Text, nullable=True)
    postal_code = Column(Text, nullable=True)
    city = Column(Text, nullable=True)
    country = Column(Text, nullable=True)
    latitude = Column(Double, nullable=True)
    longitude = Column(Double, nullable=True)

    status = Column(
        SAEnum(ServiceStatus, name="service_status"),
        server_default="draft",
        nullable=False,
        index=True,
    )

    # Provenance for imported listings; null for manually created ones.
    source = Column(Text, nullable=True)
    external_id = Column(Text, nullable=True)

    created_at = Column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Unidirectional: we intentionally do not add a `services` relationship to
    # User, to keep the shared user model untouched.
    owner = relationship("User", foreign_keys=[owner_user_id])

    contacts = relationship(
        ServiceContact,
        back_populates="service",
        cascade="all, delete-orphan",
        order_by="ServiceContact.display_order",
    )

    category_links = relationship(
        ServiceCategory,
        back_populates="service",
        cascade="all, delete-orphan",
    )

    @property
    def primary_category_link(self) -> ServiceCategory | None:
        """The primary category link, if one is set."""
        for link in self.category_links:
            if link.is_primary:
                return link
        return None
