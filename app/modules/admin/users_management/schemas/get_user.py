from pydantic import BaseModel, Field
from typing import Dict, Optional
from datetime import datetime

class FullUserResponse(BaseModel):
    """
    Complete User model response including internal counters and external IDs.
    """
    # Eurobot-owned identifier
    counter: Optional[int] = Field(None, description="Optional Eurobot-owned counter")

    # Shared primary key
    user_id: int = Field(..., description="Telegram User ID")
    accounting_code: Optional[str] = None
    
    # Profile Info
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    nickname: Optional[str] = None
    
    # Contact Info
    phone_number: Optional[str] = None
    whatsapp_number: Optional[str] = None
    country: Optional[str] = None
    
    # Auth & Status
    #
    # The password hash is deliberately NOT part of this response. It was
    # previously included "for completeness", which meant every admin list and
    # detail request shipped bcrypt hashes to the browser, and made the hash
    # queryable as a LIKE filter, which is a slow oracle. No workflow needs it:
    # authentication reads the hash straight from the database, and password
    # changes go through the auth endpoints rather than an admin read.
    mode: Optional[str] = None
    
    # Booleans
    is_ban: bool
    is_registered: bool
    chat_not_found: bool
    is_in_eurobot: bool
    is_in_hilfen_bot: bool

    # Numbers
    score: int
    ban_time: int
    join_date: Optional[int] = None

    # Media / External Refs
    profile_path: Optional[str] = None
    telegram_message_id: Optional[str] = None
    group_message_id: Optional[str] = None
    public_message_id: Optional[str] = None
    public_group_message_id: Optional[str] = None

    # Hilfen-specific fields
    hilfen_id: Optional[int] = None
    hilfen_status: Optional[str] = None
    hilfen_date_join: Optional[int] = None
    hilfen_command: Optional[str] = None
    hilfen_data: Optional[str] = None
    hilfen_id_card_photo: Optional[str] = None
    hilfen_all_projects: Optional[int] = None
    hilfen_all_projects_done: Optional[int] = None
    hilfen_limits_time: Optional[int] = None
    hilfen_message_id: Optional[int] = None
    hilfen_group_message_id: Optional[int] = None

    # Timestamps
    updated_at: datetime
    channel_updated_at: Optional[datetime] = None
    field_updated_at: Dict[str, Optional[datetime]]

    class Config:
        from_attributes = True # Maps SQLAlchemy model -> Pydantic
