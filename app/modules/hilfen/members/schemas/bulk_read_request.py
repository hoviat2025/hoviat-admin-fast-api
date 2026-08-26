from pydantic import BaseModel, Field
from typing import List

class BulkReadMembersRequest(BaseModel):
    # Enforce max_items to prevent DB overloading
    user_ids: List[int] = Field(
        ...,
        min_items=1,
        max_items=1000,
        description="List of user IDs (Max 1000 per request)"
    )