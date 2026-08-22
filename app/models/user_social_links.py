from sqlalchemy import Column, BigInteger, String, Integer, TIMESTAMP, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.models.base import Base


class UserSocialLink(Base):
    """
    A single social media / external link attached to a user's profile.
    A user may have many of these (instagram, linkedin, personal site, ...).
    """
    __tablename__ = "user_social_links"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    user_id = Column(
        BigInteger,
        ForeignKey("users_eurobot.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Lowercase platform identifier, e.g. "instagram", "linkedin", "website"
    platform = Column(String, nullable=False)

    # The fully-qualified URL to the profile
    url = Column(String, nullable=False)

    # Optional free-text label/handle (e.g. "@handle")
    label = Column(String, nullable=True)

    # Ordering within the user's list of links
    position = Column(Integer, server_default="0", nullable=False)

    created_at = Column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user = relationship("User", back_populates="social_links")
