from sqlalchemy import Column, Integer, String, Boolean, BigInteger, TIMESTAMP, text
from sqlalchemy.sql import func
from app.models.base import Base  # <--- Imported from the proper location

class User(Base):
    __tablename__ = "users_eurobot"

    # Primary Key
    counter = Column(Integer, primary_key=True) 

    # Identifiers
    user_id = Column(BigInteger, unique=True, nullable=True)
    accounting_code = Column(String, nullable=True)
    
    # Profile Info
    username = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    nickname = Column(String, nullable=True)
    
    # Contact Info
    phone_number = Column(String, nullable=True)
    whatsapp_number = Column(String, nullable=True)
    country = Column(String, nullable=True)
    
    # Auth & Status
    password = Column(String, nullable=True)
    mode = Column(String, nullable=True)
    
    # Booleans
    is_ban = Column(Boolean, default=False)
    is_registered = Column(Boolean, default=False)
    chat_not_found = Column(Boolean, default=False)

    # Numbers / Timestamps
    score = Column(Integer, default=0)
    ban_time = Column(BigInteger, default=0)
    join_date = Column(BigInteger, nullable=True)

    # Media / External Refs
    profile_path = Column(String, nullable=True)
    telegram_message_id = Column(String, nullable=True)
    group_message_id = Column(String, nullable=True)
    public_message_id = Column(String, nullable=True)
    public_group_message_id = Column(String, nullable=True)

    # Timestamps
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    channel_updated_at = Column(TIMESTAMP(timezone=True), nullable=True)