from sqlalchemy import Column, Integer
from app.models.base import Base

class TelegramMessage(Base):
    __tablename__ = "telegram_messages"

    telegram_message_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=True)
    group_message_id = Column(Integer, nullable=True)
    public_message_id = Column(Integer, nullable=True)
    public_group_message_id = Column(Integer, nullable=True)