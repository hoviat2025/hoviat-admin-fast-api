from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ProfileSearchParams(BaseModel):
    """
    Query parameters for searching public user profiles.
    Used as a FastAPI dependency to validate incoming GET requests.
    """
    model_config = ConfigDict(extra="ignore")

    # Global text search across multiple fields
    q: Optional[str] = Field(
        default=None,
        description="Global search across username, nickname, first_name, last_name, bio, and occupation.",
    )

    # Text Fields (Partial / Contains Match)
    username: Optional[str] = None
    nickname: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    bio: Optional[str] = None
    occupation: Optional[str] = None

    # Exact Match Fields
    country: Optional[str] = None
    is_ban: Optional[bool] = None
    is_registered: Optional[bool] = None

    # Pagination
    page: int = Field(default=1, ge=1, description="Page number, starting at 1")
    size: int = Field(default=20, ge=1, le=100, description="Items per page (max 100)")
