from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
from datetime import datetime

# 1. INPUT: Exact match to your CURL command
class BotUpdateMemberRequest(BaseModel):
    user_id: int = Field(..., description="The ID of the user to update")
    
    # Pydantic will automatically convert string "0" to int 0, which is great for you.
    counter: Optional[int] = None
    accounting_code: Optional[str] = None
    ban_time: Optional[int] = None 
    country: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_ban: Optional[bool] = None
    is_registered: Optional[bool] = None
    join_date: Optional[int] = None
    password: Optional[str] = None
    phone_number: Optional[str] = None
    score: Optional[int] = None
    whatsapp_number: Optional[str] = None
    
    model_config = ConfigDict(
        populate_by_name=True,
        # REMOVED alias_generator=to_pascal (This was the danger zone!)
    )

# 2. OUTPUT: The Full User Object
class BotUserResponse(BaseModel):
    # Identifiers
    user_id: int
    counter: Optional[int] = None # Marked optional just in case DB has nulls
    
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
        # REMOVED alias_generator here too. 
        # Output keys will now be "user_id", "first_name", etc.
    )