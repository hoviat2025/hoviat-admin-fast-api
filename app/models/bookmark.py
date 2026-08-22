from sqlalchemy import Column, BigInteger, TIMESTAMP, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.models.base import Base


class Bookmark(Base):
    """
    Represents a Many-to-Many relationship between Users with additional metadata (timestamp).
    This allows users to save/bookmark other users' profiles.
    """
    __tablename__ = "bookmarks"

    # Composite Primary Key Component 1: The user who is performing the action
    bookmarker_id = Column(
        BigInteger,
        ForeignKey("users_eurobot.user_id", ondelete="CASCADE"),
        primary_key=True,
    )

    # Composite Primary Key Component 2: The user who is being saved
    bookmarked_user_id = Column(
        BigInteger,
        ForeignKey("users_eurobot.user_id", ondelete="CASCADE"),
        primary_key=True,
    )

    # Metadata
    created_at = Column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    # foreign_keys is required here because both keys point to the same User table.
    bookmarker = relationship(
        "User", foreign_keys=[bookmarker_id], back_populates="bookmarks_created"
    )

    bookmarked_user = relationship(
        "User", foreign_keys=[bookmarked_user_id], back_populates="bookmarks_received"
    )
