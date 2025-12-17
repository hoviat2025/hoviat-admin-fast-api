from pydantic import BaseModel, Field, ConfigDict, BeforeValidator
from typing import List, Annotated, Any

# Import your other schemas
from app.modules.eurobot.members.schemas.insert_request import BotInsertMemberRequest
from app.modules.eurobot.members.schemas.bot_user_dto import BotUserResponse

# --- 1. Define the String Conversion Logic (Same as in your DTO) ---
def force_to_string(v: Any) -> str:
    """Converts int to string before validation to ensure JSON safety."""
    if v is None:
        return None
    return str(v)

StringifiedInt = Annotated[str, BeforeValidator(force_to_string)]
# -------------------------------------------------------------------

class BulkUpsertMembersRequest(BaseModel):
    users_info: List[BotInsertMemberRequest] = Field(
        ..., 
        min_items=1, 
        max_items=1000, 
        description="List of user objects to upsert (Insert if new, Update if user_id exists)."
    )
    
    model_config = ConfigDict(extra='ignore')

class BulkUpsertSuccessItem(BaseModel):
    index: int
    status: str = "success"
    
    # --- 2. Apply the fix here ---
    user_id: StringifiedInt 
    
    data: BotUserResponse

class BulkUpsertFailedItem(BaseModel):
    index: int
    status: str = "error"
    code: str
    message: str

class BulkUpsertResultData(BaseModel):
    successful: List[BulkUpsertSuccessItem]
    failed: List[BulkUpsertFailedItem]