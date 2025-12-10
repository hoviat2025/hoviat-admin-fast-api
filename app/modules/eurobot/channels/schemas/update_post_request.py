from pydantic import BaseModel, Field

class UpdateChannelPostRequest(BaseModel):
    user_id: int = Field(..., description="The ID of the user to update in the channel")