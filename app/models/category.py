from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    CheckConstraint,
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
    A category in a two-level directory. Roots have no parents; a child can
    belong to several roots. parent_id retains its primary root for compatibility.

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

    parent_links = relationship(
        "CategoryParent", foreign_keys="CategoryParent.category_id",
        cascade="all, delete-orphan",
    )

    @property
    def level(self) -> int:
        return 1 if self.parent_id is None else 2

    @property
    def parent_ids(self) -> list[int]:
        # Repositories eager-load links. Avoid implicit asynchronous IO for
        # unrelated code that only needs a category label or primary parent.
        ids = {link.parent_id for link in self.__dict__.get("parent_links", [])}
        if self.parent_id is not None:
            ids.add(self.parent_id)
        return sorted(ids, key=lambda value: (value != self.parent_id, value))


class CategoryParent(Base):
    """Membership of a level-two category under one root category."""

    __tablename__ = "category_parents"
    __table_args__ = (CheckConstraint("category_id <> parent_id", name="category_parent_not_self"),)

    category_id = Column(
        BigInteger, ForeignKey("categories.id", ondelete="CASCADE"), primary_key=True,
    )
    parent_id = Column(
        BigInteger, ForeignKey("categories.id", ondelete="RESTRICT"), primary_key=True,
        index=True,
    )
