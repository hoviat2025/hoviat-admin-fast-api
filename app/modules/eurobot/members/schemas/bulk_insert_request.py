from pydantic import BaseModel, Field, ConfigDict
from typing import List
from app.modules.eurobot.members.schemas.insert_request import BotInsertMemberRequest
from app.modules.eurobot.members.schemas.bot_user_dto import BotUserResponse

class BulkInsertMembersRequest(BaseModel):
    users_info: List[BotInsertMemberRequest] = Field(
        ..., 
        min_items=1, 
        max_items=1000, 
        description="List of user objects to insert."
    )
    
    model_config = ConfigDict(extra='ignore')

class BulkInsertSuccessItem(BaseModel):
    index: int
    status: str = "success"
    user_id: int
    data: BotUserResponse

class BulkInsertFailedItem(BaseModel):
    index: int
    status: str = "error"
    code: str
    message: str

class BulkInsertResultData(BaseModel):
    successful: List[BulkInsertSuccessItem]
    failed: List[BulkInsertFailedItem]