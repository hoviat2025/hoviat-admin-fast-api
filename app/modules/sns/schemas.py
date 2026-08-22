from typing import Optional

from pydantic import BaseModel


class SocialLinkResponse(BaseModel):
    """
    A single social media / external link exposed on a user profile.
    Shared between the account and profiles features.
    """
    id: int
    platform: str
    url: str
    label: Optional[str] = None

    class Config:
        from_attributes = True
