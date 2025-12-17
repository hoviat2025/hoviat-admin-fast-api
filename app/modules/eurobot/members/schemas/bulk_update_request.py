from pydantic import BaseModel, Field, ConfigDict, BeforeValidator
from typing import List, Annotated, Any

from app.modules.eurobot.members.schemas.update_request import BotUpdateMemberRequest
from app.modules.eurobot.members.schemas.bot_user_dto import BotUserResponse

# --- 1. Define String Conversion Logic ---
def force_to_string(v: Any) -> str:
    """Converts int to string before validation to ensure JSON safety."""
    if v is None:
        return None
    return str(v)

StringifiedInt = Annotated[str, BeforeValidator(force_to_string)]
# -----------------------------------------

class BulkUpdateMembersRequest(BaseModel):
    users_info: List[BotUpdateMemberRequest] = Field(
        ..., 
        min_items=1, 
        max_items=1000, 
        description="List of user objects to update. user_id is required in each object."
    )
    
    model_config = ConfigDict(extra='ignore')

class BulkUpdateSuccessItem(BaseModel):
    index: int
    status: str = "success"
    
    # --- 2. Apply the fix here ---
    user_id: StringifiedInt
    
    data: BotUserResponse

class BulkUpdateFailedItem(BaseModel):
    index: int
    status: str = "error"
    code: str
    message: str

class BulkUpdateResultData(BaseModel):
    successful: List[BulkUpdateSuccessItem]
    failed: List[BulkUpdateFailedItem]