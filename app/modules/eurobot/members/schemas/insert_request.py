from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, Union

class BotInsertMemberRequest(BaseModel):
    # Identifiers
    user_id: int = Field(..., description="The Telegram User ID")
    counter: Optional[int] = Field(None, description="Primary key counter")
    accounting_code: Optional[str] = None

    # Profile
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    username: Optional[str] = None
    nickname: Optional[str] = None
    
    # Contact
    phone_number: Optional[str] = None
    whatsapp_number: Optional[str] = None
    country: Optional[str] = None

    # Status & Auth
    password: Optional[str] = None
    mode: Optional[str] = None
    is_ban: bool = False
    is_registered: bool = False
    
    # Numbers/Dates 
    score: int = 0
    ban_time: Union[int, str] = 0 
    join_date: Optional[Union[int, str]] = None

    # Security Config:
    # populate_by_name=True -> Allows using field names or aliases
    # extra='ignore' -> CRITICAL: If client sends "admin": true or "hack": 1, 
    #                   Pydantic silently discards them. They never reach the Service/DB.
    model_config = ConfigDict(populate_by_name=True, extra='ignore')