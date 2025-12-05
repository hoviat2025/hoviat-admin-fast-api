from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
from datetime import datetime

class SharedUserResponse(BaseModel):
    # --- Primary Keys & IDs ---
    counter: int = Field(..., description="Internal Database Primary Key")
    user_id: int = Field(..., description="Telegram User ID")
    
    # --- Profile Info ---
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    nickname: Optional[str] = None
    
    # --- Contact Info ---
    phone_number: Optional[str] = None
    whatsapp_number: Optional[str] = None
    country: Optional[str] = None
    
    # --- Auth & Status ---
    # We include password because your JSON sample showed it (e.g., "9999"). 
    # If this is sensitive, you can remove it later.
    password: Optional[str] = None 
    mode: Optional[str] = None
    accounting_code: Optional[str] = None
    
    # --- Flags (Booleans) ---
    is_ban: bool = False
    is_registered: bool = False
    chat_not_found: bool = False

    # --- Numbers / Metrics ---
    score: int = 0
    ban_time: Optional[int] = 0
    # Your DB stores join_date as BigInt (timestamp integer), not DateTime object
    join_date: Optional[int] = None 

    # --- Media / External Refs ---
    profile_path: Optional[str] = None
    
    # --- Message IDs (Text fields in DB) ---
    telegram_message_id: Optional[str] = None
    group_message_id: Optional[str] = None
    public_message_id: Optional[str] = None
    public_group_message_id: Optional[str] = None

    # --- Timestamps ---
    # These are proper datetime objects in the DB
    updated_at: datetime
    channel_updated_at: Optional[datetime] = None

    # --- Configuration ---
    model_config = ConfigDict(
        from_attributes=True,      # Reads from SQLAlchemy Model
        populate_by_name=True      # Allows field mapping
    )