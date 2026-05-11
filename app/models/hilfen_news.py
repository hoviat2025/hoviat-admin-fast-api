# app/models/hilfen_news.py
from sqlalchemy import Column, BigInteger, String, Text, TIMESTAMP,Integer
from sqlalchemy.sql import func
from app.models.base import Base

class HilfenNews(Base):
    __tablename__ = "hilfen_news"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False)
    news_type = Column(String(50))
    city = Column(String(255))
    news_text = Column(Text)             
    media = Column(Text)
    media_group_id = Column(Text)
    status = Column(String(50), default='draft')
    preview_message_id = Column(BigInteger)
    admin_check_message_id = Column(BigInteger)
    admin_check_chat_id = Column(BigInteger)
    decline_message = Column(Text)
    main_channel_message_id = Column(BigInteger)
    main_channel_id = Column(BigInteger)
    group_chat_id = Column(BigInteger)
    group_message_id = Column(BigInteger)
    contact_group_message_id = Column(BigInteger)
    user_handle_message_id = Column(BigInteger)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    sub_type = Column(Text)
    additional_features = Column(Text, default="{}")
