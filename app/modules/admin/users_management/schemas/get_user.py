from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class FullUserResponse(BaseModel):
    """
    Complete User model response including internal counters and external IDs.
    """
    # Primary Key
    counter: int = Field(..., description="Internal Database ID")

    # Identifiers
    user_id: Optional[int] = Field(None, description="Telegram User ID")
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
    # Note: We return the hashed password string if it exists, usually not recommended for security 
    # but requested to return "everything". Frontend should treat this carefully.
    password: Optional[str] = None 
    mode: Optional[str] = None
    
    # Booleans
    is_ban: bool
    is_registered: bool
    chat_not_found: bool

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

    # Timestamps
    updated_at: datetime
    channel_updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True # Maps SQLAlchemy model -> Pydantic