from pydantic import BaseModel


class BookmarkActionResponse(BaseModel):
    user_id: int
    bookmarked: bool
