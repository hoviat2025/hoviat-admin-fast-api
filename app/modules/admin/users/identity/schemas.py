from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
from datetime import datetime

class UserIdentityResponse(BaseModel):
    # We only include fields relevant to "Identity"
    # We skip "telegram_message_id" because the Admin human doesn't care about that.
    
    user_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone_number: Optional[str] = None
    country: Optional[str] = None
    
    # Handling Dates
    join_date: Optional[int] = None
    updated_at: datetime

    # This tells Pydantic: "Trust me, I can read this data from a SQLAlchemy Class"
    model_config = ConfigDict(from_attributes=True)
