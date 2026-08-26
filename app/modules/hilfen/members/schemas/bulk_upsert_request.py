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

class BulkUpsertMembersRequest(BaseModel):
    users_info: List[HilfenInsertMemberRequest] = Field(
        ...,
        min_items=1,
        max_items=1000,
        description="List of Hilfen user objects to upsert (Insert if new, Update if user_id exists)."
    )

    model_config = ConfigDict(extra='ignore')

class BulkUpsertSuccessItem(BaseModel):
    index: int
    status: str = "success"
    user_id: StringifiedInt
    data: HilfenUserResponse

class BulkUpsertFailedItem(BaseModel):
    index: int
    status: str = "error"
    code: str
    message: str

class BulkUpsertResultData(BaseModel):
    successful: List[BulkUpsertSuccessItem]
    failed: List[BulkUpsertFailedItem]