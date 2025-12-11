from pydantic import BaseModel, ConfigDict
from typing import Optional, Any

class QuoteReplyInfoResponse(BaseModel):
    # Explicit Fields
    channel_message_id: Optional[int] = None
    channel_id: Optional[int] = None
    
    group_message_id: Optional[int] = None
    group_id: Optional[int] = None
    
    public_group_message_id: Optional[int] = None
    public_group_id: Optional[int] = None
    
    public_message_id: Optional[int] = None
    public_channel_id: Optional[int] = None

    # This configuration allows 'components' fields (e.g., { "id": 5 }) 
    # to coexist at the top level of this model.
    model_config = ConfigDict(
        extra='allow',
        from_attributes=True
    )