"""Private snapshots of merged directory records; never part of public queries."""
from sqlalchemy import BigInteger, Column, ForeignKey, JSON, Text, TIMESTAMP, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from app.models.base import Base


class ServiceDuplicateArchive(Base):
    __tablename__ = "service_duplicate_archives"
    __table_args__ = (UniqueConstraint("source", "external_id"),)
    original_id = Column(BigInteger, primary_key=True, autoincrement=False)
    survivor_id = Column(BigInteger, ForeignKey("services.id", ondelete="SET NULL"), index=True)
    source = Column(Text)
    external_id = Column(Text)
    snapshot = Column(JSON().with_variant(JSONB, "postgresql"), nullable=False)
    merged_by = Column(Text, nullable=False)
    reason = Column(Text, nullable=False)
    archived_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
