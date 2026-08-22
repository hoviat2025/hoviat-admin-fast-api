from sqlalchemy import Column, Integer, String, Boolean, BigInteger, TIMESTAMP, Text, text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.models.base import Base

# Explicitly importing related models ensures they are registered in
# SQLAlchemy's Base.metadata before the ORM mapper initializes.
from app.models.user_privacy_settings import UserPrivacySettings
from app.models.user_social_links import UserSocialLink
from app.models.bookmark import Bookmark


FIELD_TIMESTAMP_FIELDS = (
    "counter",
    "user_id",
    "accounting_code",
    "username",
    "first_name",
    "last_name",
    "nickname",
    "bio",
    "occupation",
    "phone_number",
    "whatsapp_number",
    "country",
    "password",
    "mode",
    "is_ban",
    "is_registered",
    "chat_not_found",
    "is_in_eurobot",
    "is_in_hilfen_bot",
    "score",
    "ban_time",
    "join_date",
    "profile_path",
    "telegram_message_id",
    "group_message_id",
    "public_message_id",
    "public_group_message_id",
    "hilfen_id",
    "hilfen_status",
    "hilfen_date_join",
    "hilfen_command",
    "hilfen_data",
    "hilfen_id_card_photo",
    "hilfen_all_projects",
    "hilfen_all_projects_done",
    "hilfen_limits_time",
    "hilfen_message_id",
    "hilfen_group_message_id",
)

class User(Base):
    __tablename__ = "users_eurobot"

    # Shared Telegram identity and primary key
    user_id = Column(BigInteger, primary_key=True)

    # Eurobot-owned identifier. Hilfen-only users may not have one yet.
    counter = Column(BigInteger, unique=True, nullable=True)
    accounting_code = Column(String, nullable=True)
    
    # Profile Info
    username = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    nickname = Column(String, nullable=True)
    bio = Column(Text, nullable=True)
    occupation = Column(Text, nullable=True)
    
    # Contact Info
    phone_number = Column(String, nullable=True)
    whatsapp_number = Column(String, nullable=True)
    country = Column(String, nullable=True)
    
    # Auth & Status (Eurobot)
    password = Column(String, nullable=True)
    mode = Column(String, nullable=True)
    
    # Booleans
    is_ban = Column(Boolean, default=False)
    is_registered = Column(Boolean, default=False)
    chat_not_found = Column(Boolean, default=False)
    
    # Bot Presence Identifiers
    is_in_eurobot = Column(Boolean, default=False, nullable=False)
    is_in_hilfen_bot = Column(Boolean, default=False, nullable=False)

    # Numbers / Timestamps (Eurobot)
    score = Column(Integer, default=0)
    ban_time = Column(BigInteger, default=0)
    join_date = Column(BigInteger, nullable=True)

    # Media / External Refs (Eurobot)
    profile_path = Column(String, nullable=True)
    # Identifies whether the current profile image came from Telegram or the SNS panel.
    profile_source = Column(String, nullable=True)
    telegram_message_id = Column(String, nullable=True)
    group_message_id = Column(String, nullable=True)
    public_message_id = Column(String, nullable=True)
    public_group_message_id = Column(String, nullable=True)

    # ==========================================
    # Hilfen Bot Specific Fields
    # ==========================================
    hilfen_id = Column(BigInteger, nullable=True)
    hilfen_status = Column(String, nullable=True)
    hilfen_date_join = Column(BigInteger, nullable=True)
    hilfen_command = Column(String, nullable=True)
    hilfen_data = Column(String, nullable=True)
    hilfen_id_card_photo = Column(String, nullable=True)
    hilfen_all_projects = Column(Integer, default=0)
    hilfen_all_projects_done = Column(Integer, default=0)
    hilfen_limits_time = Column(BigInteger, default=0)
    
    # Internal messaging anchors (not exposed via Pydantic API layer)
    hilfen_message_id = Column(BigInteger, nullable=True)
    hilfen_group_message_id = Column(BigInteger, nullable=True)

    # Timestamps
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    channel_updated_at = Column(TIMESTAMP(timezone=True), nullable=True)

    # Per-field modification timestamps. PostgreSQL owns these values; API
    # clients may read them but cannot supply them in write requests.
    counter_updated_at = Column(TIMESTAMP(timezone=True), nullable=True)
    user_id_updated_at = Column(TIMESTAMP(timezone=True), nullable=True)
    accounting_code_updated_at = Column(TIMESTAMP(timezone=True), nullable=True)
    username_updated_at = Column(TIMESTAMP(timezone=True), nullable=True)
    first_name_updated_at = Column(TIMESTAMP(timezone=True), nullable=True)
    last_name_updated_at = Column(TIMESTAMP(timezone=True), nullable=True)
    nickname_updated_at = Column(TIMESTAMP(timezone=True), nullable=True)
    bio_updated_at = Column(TIMESTAMP(timezone=True), nullable=True)
    occupation_updated_at = Column(TIMESTAMP(timezone=True), nullable=True)
    phone_number_updated_at = Column(TIMESTAMP(timezone=True), nullable=True)
    whatsapp_number_updated_at = Column(TIMESTAMP(timezone=True), nullable=True)
    country_updated_at = Column(TIMESTAMP(timezone=True), nullable=True)
    password_updated_at = Column(TIMESTAMP(timezone=True), nullable=True)
    mode_updated_at = Column(TIMESTAMP(timezone=True), nullable=True)
    is_ban_updated_at = Column(TIMESTAMP(timezone=True), nullable=True)
    is_registered_updated_at = Column(TIMESTAMP(timezone=True), nullable=True)
    chat_not_found_updated_at = Column(TIMESTAMP(timezone=True), nullable=True)
    is_in_eurobot_updated_at = Column(TIMESTAMP(timezone=True), nullable=True)
    is_in_hilfen_bot_updated_at = Column(TIMESTAMP(timezone=True), nullable=True)
    score_updated_at = Column(TIMESTAMP(timezone=True), nullable=True)
    ban_time_updated_at = Column(TIMESTAMP(timezone=True), nullable=True)
    join_date_updated_at = Column(TIMESTAMP(timezone=True), nullable=True)
    profile_path_updated_at = Column(TIMESTAMP(timezone=True), nullable=True)
    telegram_message_id_updated_at = Column(TIMESTAMP(timezone=True), nullable=True)
    group_message_id_updated_at = Column(TIMESTAMP(timezone=True), nullable=True)
    public_message_id_updated_at = Column(TIMESTAMP(timezone=True), nullable=True)
    public_group_message_id_updated_at = Column(TIMESTAMP(timezone=True), nullable=True)
    hilfen_id_updated_at = Column(TIMESTAMP(timezone=True), nullable=True)
    hilfen_status_updated_at = Column(TIMESTAMP(timezone=True), nullable=True)
    hilfen_date_join_updated_at = Column(TIMESTAMP(timezone=True), nullable=True)
    hilfen_command_updated_at = Column(TIMESTAMP(timezone=True), nullable=True)
    hilfen_data_updated_at = Column(TIMESTAMP(timezone=True), nullable=True)
    hilfen_id_card_photo_updated_at = Column(TIMESTAMP(timezone=True), nullable=True)
    hilfen_all_projects_updated_at = Column(TIMESTAMP(timezone=True), nullable=True)
    hilfen_all_projects_done_updated_at = Column(TIMESTAMP(timezone=True), nullable=True)
    hilfen_limits_time_updated_at = Column(TIMESTAMP(timezone=True), nullable=True)
    hilfen_message_id_updated_at = Column(TIMESTAMP(timezone=True), nullable=True)
    hilfen_group_message_id_updated_at = Column(TIMESTAMP(timezone=True), nullable=True)

    @property
    def field_updated_at(self) -> dict:
        """Expose per-field timestamps as one stable API metadata object."""

        return {
            field: getattr(self, f"{field}_updated_at")
            for field in FIELD_TIMESTAMP_FIELDS
        }

    # --------------------------------------------------------------------------
    # Relationships
    # --------------------------------------------------------------------------

    # Privacy Settings (One-to-One)
    # Access: user.privacy_settings.phone_number_visibility
    privacy_settings = relationship(
        UserPrivacySettings,
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )

    # Social Media Links (One-to-Many)
    # Access: user.social_links
    social_links = relationship(
        UserSocialLink,
        back_populates="user",
        cascade="all, delete-orphan",
        order_by="UserSocialLink.position",
    )

    # Bookmarks Created (One-to-Many)
    # Access: user.bookmarks_created
    bookmarks_created = relationship(
        Bookmark,
        foreign_keys=[Bookmark.bookmarker_id],
        back_populates="bookmarker",
        cascade="all, delete-orphan",
    )

    # Bookmarks Received (One-to-Many)
    # Access: user.bookmarks_received
    bookmarks_received = relationship(
        Bookmark,
        foreign_keys=[Bookmark.bookmarked_user_id],
        back_populates="bookmarked_user",
        cascade="all, delete-orphan",
    )

