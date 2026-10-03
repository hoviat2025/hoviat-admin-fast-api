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

    # Four independent Iranian/Persian relevance signals.
    #
    # These describe WHO or WHAT a service is connected to. They say nothing
    # about where the service is: this directory lists services located in
    # Germany, and Iranian/Persian relevance is an attribute of the listing, not
    # a geography. A service may have none of these set.
    #
    # Tri-state on purpose: True = explicitly yes, False = explicitly no,
    # None = not assessed. Imported and curated data frequently does not know,
    # and silently storing "unknown" as False would fabricate an answer and make
    # the field useless for data-quality filtering later.
    persian_owned = Column(Boolean, nullable=True)
    # Whether the person actually providing the service is Iranian/Persian,
    # which is independent of who owns the business.
    persian_provider = Column(Boolean, nullable=True)
    # Whether a customer can be served in Persian. Unrelated to origin.
    persian_language = Column(Boolean, nullable=True)
    # Whether the product/service itself is Iranian/Persian in nature.
    persian_service = Column(Boolean, nullable=True)

    # Structured location (searchable), deliberately not a contact row.
    #
    # The directory is PRESENTED Germany-first, but the model is international:
    # country_code is an ISO-3166-1 alpha-2 code and is deliberately not
    # constrained to DE, so adding a country is data, not a migration.
    #
    # `state` is the generic concept "first-level administrative region": a
    # Bundesland in Germany, a canton in Switzerland, a province in Canada. It is
    # NOT renamed to anything Germany-specific. Where a country has a known
    # vocabulary (currently only DE) the stored value is canonicalised on write;
    # see CountryState.
    address = Column(Text, nullable=True)
    postal_code = Column(Text, nullable=True)
    city = Column(Text, nullable=True)
    # First-level administrative region. Canonical spelling when the country has
    # a vocabulary; otherwise free text.
    state = Column(Text, nullable=True)
    # ISO-3166-1 alpha-2, uppercase. NULL means "not stated".
    country_code = Column(Text, nullable=True)
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
