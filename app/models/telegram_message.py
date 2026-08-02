from sqlalchemy import Column, Integer, BigInteger
from app.models.base import Base

class TelegramMessage(Base):
    __tablename__ = "telegram_messages"

    telegram_message_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(BigInteger, nullable=True)
    group_message_id = Column(Integer, nullable=True)
    public_message_id = Column(Integer, nullable=True)
    public_group_message_id = Column(Integer, nullable=True)
    hilfen_message_id = Column(Integer, nullable=True)
    hilfen_group_message_id = Column(Integer, nullable=True)