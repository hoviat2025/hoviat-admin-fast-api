import enum
from sqlalchemy import Column, Boolean, BigInteger, TIMESTAMP, ForeignKey, Enum as SAEnum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.models.base import Base


class PrivacyScope(str, enum.Enum):
    """
    Enumeration for visibility levels.
    Matches the PostgreSQL TYPE 'privacy_scope'.
    """
    public = "public"
    private = "private"


class UserPrivacySettings(Base):
    """
    Stores visibility permissions for specific user profile fields.
    Linked 1-to-1 with the users_eurobot table.
    """
    __tablename__ = "user_privacy_settings"

    # Primary Key serves as Foreign Key to the User table
    # ondelete="CASCADE" ensures privacy settings are removed if the user is deleted
    user_id = Column(
        BigInteger,
        ForeignKey("users_eurobot.user_id", ondelete="CASCADE"),
        primary_key=True,
    )

    # Global visibility toggle
    # If False, the profile is hidden entirely regardless of specific settings
    is_profile_discoverable = Column(Boolean, server_default="true", nullable=False)

    # Identity Information
    profile_picture_visibility = Column(
        SAEnum(PrivacyScope, name="privacy_scope"),
        server_default="private",
        nullable=False,
    )

    username_visibility = Column(
        SAEnum(PrivacyScope, name="privacy_scope"),
        server_default="private",
        nullable=False,
    )

    first_name_visibility = Column(
        SAEnum(PrivacyScope, name="privacy_scope"),
        server_default="private",
        nullable=False,
    )

    last_name_visibility = Column(
        SAEnum(PrivacyScope, name="privacy_scope"),
        server_default="private",
        nullable=False,
    )

    # Only the nickname is public by default; every other field must be opted in.
    nickname_visibility = Column(
        SAEnum(PrivacyScope, name="privacy_scope"),
        server_default="public",
        nullable=False,
    )

    country_visibility = Column(
        SAEnum(PrivacyScope, name="privacy_scope"),
        server_default="private",
        nullable=False,
    )

    # Contact Information (Defaults to Private for security)
    phone_number_visibility = Column(
        SAEnum(PrivacyScope, name="privacy_scope"),
        server_default="private",
        nullable=False,
    )

    whatsapp_number_visibility = Column(
        SAEnum(PrivacyScope, name="privacy_scope"),
        server_default="private",
        nullable=False,
    )

    # Self-presentation fields
    bio_visibility = Column(
        SAEnum(PrivacyScope, name="privacy_scope"),
        server_default="private",
        nullable=False,
    )

    social_links_visibility = Column(
        SAEnum(PrivacyScope, name="privacy_scope"),
        server_default="private",
        nullable=False,
    )

    # Record Metadata
    updated_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationship to Parent User
    user = relationship("User", back_populates="privacy_settings")
