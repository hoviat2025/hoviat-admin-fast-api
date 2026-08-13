from sqlalchemy import BigInteger, Boolean, Column, DateTime, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from app.models.base import Base


class AdminAuditLog(Base):
    """Durable audit record for administrator actions."""

    __tablename__ = "admin_audit_logs"

    id = Column(BigInteger, primary_key=True)
    admin_id = Column(Integer, nullable=False, index=True)
    admin_username = Column(String, nullable=False)
    action = Column(String, nullable=False, index=True)
    target_type = Column(String, nullable=False, index=True)
    target_id = Column(String, nullable=False, index=True)
    changes = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    sync_channels = Column(Boolean, nullable=True)
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
