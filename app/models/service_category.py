from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    ForeignKey,
    TIMESTAMP,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import Base


class ServiceCategory(Base):
    """
    Many-to-many link between a service and a category.

    A service may carry several categories; exactly one may be flagged primary.
    "At most one primary per service" is enforced by the database (a partial
    unique index on service_id WHERE is_primary), not only by application code.

    The service FK cascades, so deleting a service removes its links. The
    category FK is RESTRICT, so a category that is in use cannot be deleted.
    """
    __tablename__ = "service_categories"

    service_id = Column(
        BigInteger,
        ForeignKey("services.id", ondelete="CASCADE"),
        primary_key=True,
    )
    category_id = Column(
        BigInteger,
        ForeignKey("categories.id", ondelete="RESTRICT"),
        primary_key=True,
        index=True,
    )
    is_primary = Column(Boolean, server_default="false", nullable=False)

    created_at = Column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    service = relationship("Service", back_populates="category_links")
    category = relationship("Category", back_populates="service_links")
