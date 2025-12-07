from pydantic import BaseModel, ConfigDict, Field
from typing import Optional

class BotUpdateMemberRequest(BaseModel):
    user_id: int = Field(..., description="The ID of the user to update")
    
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
    
    model_config = ConfigDict(populate_by_name=True)