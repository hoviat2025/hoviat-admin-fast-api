from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from app.modules.sns.schemas import SocialLinkResponse
from app.modules.sns.utils import assemble_profile_url


class SingleProfileResponse(BaseModel):
    """
    The public-facing data structure for a single user profile.
    All fields are Optional because privacy settings might hide them.
    """
    user_id: int = Field(..., description="The unique identifier of the user.")

    # Status Flags (Always visible)
    is_ban: bool
    is_registered: bool
    join_date: Optional[int] = None

    # Identifiers
    username: Optional[str] = None
    nickname: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None

    # Self-presentation
    bio: Optional[str] = None
    social_links: Optional[List[SocialLinkResponse]] = None

    # Contact Info
    phone_number: Optional[str] = None
    whatsapp_number: Optional[str] = None
    country: Optional[str] = None

    # Media
    profile_url: Optional[str] = None

    @field_validator("profile_url", mode="before")
    @classmethod
    def assemble_full_url(cls, value: Optional[str]) -> Optional[str]:
        return assemble_profile_url(value)
