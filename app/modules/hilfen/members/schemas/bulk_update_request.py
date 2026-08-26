from pydantic import BaseModel, Field, ConfigDict, BeforeValidator
from typing import List, Annotated, Any

from app.modules.hilfen.members.schemas.request import HilfenInsertMemberRequest
from app.modules.hilfen.members.schemas.response import HilfenUserResponse

# --- 1. Define the String Conversion Logic (same as in the response DTO) ---
def force_to_string(v: Any) -> str:
    """Converts int to string before validation to ensure JSON safety."""
    if v is None:
        return None
    return str(v)

StringifiedInt = Annotated[str, BeforeValidator(force_to_string)]
# -------------------------------------------------------------------

class BulkUpdateMembersRequest(BaseModel):
    users_info: List[HilfenInsertMemberRequest] = Field(
        ...,
        min_items=1,
        max_items=1000,
        description="List of Hilfen user objects to update. user_id is required in each object."
    )

    model_config = ConfigDict(extra='ignore')

class BulkUpdateSuccessItem(BaseModel):
    index: int
    status: str = "success"
    user_id: StringifiedInt
    data: HilfenUserResponse

class BulkUpdateFailedItem(BaseModel):
    index: int
    status: str = "error"
    code: str
    message: str

class BulkUpdateResultData(BaseModel):
    successful: List[BulkUpdateSuccessItem]
    failed: List[BulkUpdateFailedItem]