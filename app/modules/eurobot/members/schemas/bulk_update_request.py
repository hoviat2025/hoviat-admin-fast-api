from pydantic import BaseModel, Field, ConfigDict
from typing import List
from app.modules.eurobot.members.schemas.update_request import BotUpdateMemberRequest
from app.modules.eurobot.members.schemas.bot_user_dto import BotUserResponse

class BulkUpdateMembersRequest(BaseModel):
    users_info: List[BotUpdateMemberRequest] = Field(
        ..., 
        min_items=1, 
        max_items=1000, 
        description="List of user objects to update. user_id is required in each object."
    )
    
    # Protect the wrapper object from extra fields as well
    model_config = ConfigDict(extra='ignore')

class BulkUpdateSuccessItem(BaseModel):
    index: int
    status: str = "success"
    user_id: int
    data: BotUserResponse

class BulkUpdateFailedItem(BaseModel):
    index: int
    status: str = "error"
    code: str
    message: str

class BulkUpdateResultData(BaseModel):
    successful: List[BulkUpdateSuccessItem]
    failed: List[BulkUpdateFailedItem]