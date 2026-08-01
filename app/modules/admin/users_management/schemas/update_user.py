from pydantic import BaseModel, Field, field_validator
from typing import Optional

class UpdateUserRequest(BaseModel):
    """
    Schema for updating a user.
    Only fields defined here can be modified.
    
    Fields EXCLUDED (System/Programmatic):
    - counter (Eurobot-owned identifier)
    - join_date (Creation Timestamp)
    - updated_at (Auto-updating Timestamp)
    - channel_updated_at (System Timestamp)
    """
    
    # Identifier (Required to find the user)
    user_id: int = Field(..., description="The Telegram User ID to identify the record")

    # Editable Profile Info
    accounting_code: Optional[str] = None
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    nickname: Optional[str] = None
    
    # Editable Contact Info
    phone_number: Optional[str] = None
    whatsapp_number: Optional[str] = None
    country: Optional[str] = None
    
    # Editable Auth & Status
    password: Optional[str] = None 
    mode: Optional[str] = None
    
    # Editable Booleans
    is_ban: Optional[bool] = None
    is_registered: Optional[bool] = None
    chat_not_found: Optional[bool] = None

    # Editable Numbers
    score: Optional[int] = None
    ban_time: Optional[int] = None

    # Editable Media & External IDs
    profile_path: Optional[str] = None
    telegram_message_id: Optional[str] = None
    group_message_id: Optional[str] = None
    public_message_id: Optional[str] = None
    public_group_message_id: Optional[str] = None

    @field_validator('*')
    def empty_str_to_none(cls, v):
        """
        If a string field is sent as an empty string "", convert it to None (DB NULL).
        """
        if v == "":
            return None
        return v
