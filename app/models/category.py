from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    ForeignKey,
    Integer,
    Text,
    TIMESTAMP,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import Base


class Category(Base):
    """
    A directory category, with an optional self-referential parent so the tree
    can be two or more levels deep.

    Deletion is deliberately restrictive: the self reference and the
    service_categories link both use ON DELETE RESTRICT, so a category that has
    children or is assigned to a service cannot be deleted. Use is_active=false
    to retire one instead.
    """
    __tablename__ = "categories"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    parent_id = Column(
        BigInteger,
        ForeignKey("categories.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    name = Column(Text, nullable=False)
    slug = Column(Text, nullable=False, unique=True)
    description = Column(Text, nullable=True)
    display_order = Column(Integer, server_default="0", nullable=False)
    is_active = Column(Boolean, server_default="true", nullable=False)

    created_at = Column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    parent = relationship(
        "Category",
        remote_side=[id],
        back_populates="children",
    )
    children = relationship(
        "Category",
        back_populates="parent",
        order_by="Category.display_order",
    )

    # No delete cascade here on purpose: a category that is assigned to a
    # service must not be silently removed. Deletion is blocked at the DB level
    # (RESTRICT) and would raise rather than orphan or delete links.
    service_links = relationship("ServiceCategory", back_populates="category")
