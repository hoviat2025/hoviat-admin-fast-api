from sqlalchemy import BigInteger, Column, ForeignKey, Index, TIMESTAMP
from sqlalchemy.sql import func

from app.models.base import Base


class ServiceBookmark(Base):
    """A private saved business listing, independent of profile bookmarks."""

    __tablename__ = "service_bookmarks"
    __table_args__ = (
        Index("service_bookmarks_user_created_idx", "bookmarker_id", "created_at"),
        Index("service_bookmarks_service_idx", "service_id"),
    )

    bookmarker_id = Column(
        BigInteger,
        ForeignKey("users_eurobot.user_id", ondelete="CASCADE"),
        primary_key=True,
    )
    service_id = Column(
        BigInteger,
        ForeignKey("services.id", ondelete="CASCADE"),
        primary_key=True,
    )
    created_at = Column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
