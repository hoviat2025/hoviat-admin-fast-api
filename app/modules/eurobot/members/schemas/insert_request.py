from pydantic import BaseModel, ConfigDict, Field
from typing import Optional

class BotInsertMemberRequest(BaseModel):
    # Identifiers
    user_id: int = Field(..., description="The Telegram User ID")
    counter: Optional[int] = Field(None, description="Eurobot-owned counter")
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
    is_ban: Optional[bool] = False
    is_registered: Optional[bool] = False
    
    # Numbers/Dates 
    # CRITICAL FIX: Use 'int' strictly. 
    # This ensures Pydantic converts string inputs like "0" to integer 0 
    # BEFORE sending them to the database driver.
    score: Optional[int] = 0
    ban_time: Optional[int] = 0
    join_date: Optional[int] = None

    # extra='ignore' ensures any other fields sent in the JSON are discarded
    model_config = ConfigDict(populate_by_name=True, extra='ignore')
