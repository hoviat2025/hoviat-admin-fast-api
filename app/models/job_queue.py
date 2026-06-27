import enum
from sqlalchemy import Column, Integer, BigInteger, String, Index, Text, TIMESTAMP
from sqlalchemy.sql import func
from app.models.base import Base

class JobStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class JobPriority(int, enum.Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3  # VIP

class JobQueue(Base):
    __tablename__ = "job_queue"

    # Primary Key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Matches User.user_id exactly (BigInteger)
    user_id = Column(BigInteger, nullable=False)
    
    # Stored as standard integer in DB, fully compatible with JobPriority enum values (1, 2, 3)
    priority = Column(Integer, default=JobPriority.MEDIUM.value, nullable=False)
    
    # Declaring this as String instead of Enum avoids SQLAlchemy's Enum name-serialization bug.
    # It writes exactly 'pending', 'processing', etc. (lowercase) to the DB, satisfying the DB constraint.
    status = Column(String, default=JobStatus.PENDING.value, nullable=False)
    
    # Retry management
    attempts = Column(Integer, default=0, nullable=False)
    max_attempts = Column(Integer, default=3, nullable=False)
    error_message = Column(Text, nullable=True)
    
    # Source column matching your database alteration
    source = Column(String, default="eurobot", nullable=False)
    
    # Timestamps
    created_at = Column(
        TIMESTAMP(timezone=True), 
        server_default=func.now(), 
        nullable=False
    )
    updated_at = Column(
        TIMESTAMP(timezone=True), 
        server_default=func.now(), 
        onupdate=func.now(), 
        nullable=False
    )
    completed_at = Column(TIMESTAMP(timezone=True), nullable=True)

    # ====================================================
    # Indexes and Constraints
    # ====================================================
    __table_args__ = (
        Index(
            "idx_job_queue_fetch",
            "status",
            "priority",
            "created_at"
        ),
        Index(
            "idx_job_queue_active_user_job",
            "user_id",
            unique=True,
            postgresql_where=(status.in_([JobStatus.PENDING, JobStatus.PROCESSING]))
        ),
    )