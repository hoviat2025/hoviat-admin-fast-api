from typing import List, Optional

from pydantic import BaseModel

from app.modules.sns.schemas import SocialLinkResponse
from app.models.user_privacy_settings import PrivacyScope


class PrivacySettingsResponse(BaseModel):
    is_profile_discoverable: bool
    profile_picture_visibility: str
    username_visibility: str
    first_name_visibility: str
    last_name_visibility: str
    nickname_visibility: str
    country_visibility: str
    phone_number_visibility: str
    whatsapp_number_visibility: str
    bio_visibility: str
    social_links_visibility: str

    class Config:
        from_attributes = True


class ProfilePictureResponse(BaseModel):
    profile_url: Optional[str] = None
    profile_picture_visibility: PrivacyScope


class OwnProfileResponse(BaseModel):
    """
    The authenticated user's own, unfiltered profile.
    """
    user_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    nickname: Optional[str] = None
    bio: Optional[str] = None
    phone_number: Optional[str] = None
    whatsapp_number: Optional[str] = None
    country: Optional[str] = None
    profile_url: Optional[str] = None
    is_ban: bool
    is_registered: bool
    join_date: Optional[int] = None
    social_links: List[SocialLinkResponse] = []
    privacy: Optional[PrivacySettingsResponse] = None
