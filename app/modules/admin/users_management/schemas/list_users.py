from pydantic import BaseModel
from typing import List
from app.modules.admin.users_management.schemas.get_user import FullUserResponse

class PaginationMeta(BaseModel):
    """
    Schema for the pagination details to be placed in the 'meta' field.
    """
    total: int
    page: int
    size: int
    pages: int

# We don't need a specific "Response" class for the data anymore, 
# because StandardResponse[List[FullUserResponse]] handles the list part.