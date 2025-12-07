from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

class BotUserResponse(BaseModel):
    user_id: int
    counter: Optional[int] = None
    
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    nickname: Optional[str] = None
    phone_number: Optional[str] = None
    whatsapp_number: Optional[str] = None
    country: Optional[str] = None
    password: Optional[str] = None
    mode: Optional[str] = None
    accounting_code: Optional[str] = None
    
    is_ban: bool = False
    is_registered: bool = False
    chat_not_found: bool = False

    score: int = 0
    ban_time: int = 0
    join_date: Optional[int] = None

    profile_path: Optional[str] = None
    telegram_message_id: Optional[str] = None
    group_message_id: Optional[str] = None
    public_message_id: Optional[str] = None
    public_group_message_id: Optional[str] = None

    updated_at: datetime
    channel_updated_at: Optional[datetime] = None

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True
    )