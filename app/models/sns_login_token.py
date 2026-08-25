from sqlalchemy import Column, BigInteger, String, TIMESTAMP
from sqlalchemy.sql import func

from app.models.base import Base


class SnsLoginToken(Base):
    __tablename__ = "sns_login_tokens"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    user_id = Column(BigInteger, nullable=False)

    # SHA-256 hex digest of the issued token; raw tokens are never persisted.
    token_hash = Column(String(64), nullable=False, unique=True)

    expires_at = Column(TIMESTAMP(timezone=True), nullable=False)
    used_at = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
