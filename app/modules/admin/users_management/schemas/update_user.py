from pydantic import BaseModel, Field, field_validator
from typing import Optional

class UpdateUserRequest(BaseModel):
    """
    Schema for updating a user.
    Every user-data field can be modified except user_id, which identifies the
    record. Database-maintained update timestamps remain read-only metadata.
    """
    
    # Identifier (Required to find the user)
    user_id: int = Field(..., description="The Telegram User ID to identify the record")

    # Eurobot identity and profile
    counter: Optional[int] = None
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
    
    # Status and bot membership
    is_ban: Optional[bool] = None
    is_registered: Optional[bool] = None
    chat_not_found: Optional[bool] = None
    is_in_eurobot: Optional[bool] = None
    is_in_hilfen_bot: Optional[bool] = None

    # Editable Numbers
    score: Optional[int] = None
    ban_time: Optional[int] = None
    join_date: Optional[int] = None

    # Editable Media & External IDs
    profile_path: Optional[str] = None
    telegram_message_id: Optional[str] = None
    group_message_id: Optional[str] = None
    public_message_id: Optional[str] = None
    public_group_message_id: Optional[str] = None

    # Hilfen data
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

    @field_validator('*')
    def empty_str_to_none(cls, v):
        """
        If a string field is sent as an empty string "", convert it to None (DB NULL).
        """
        if v == "":
            return None
        return v
