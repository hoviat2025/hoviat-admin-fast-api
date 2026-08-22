from typing import List, Optional

from pydantic import BaseModel, ConfigDict

from app.models.user_privacy_settings import PrivacyScope


class UpdateProfileRequest(BaseModel):
    """
    PATCH body for the authenticated user's own profile fields.
    Only supplied fields are updated; a supplied null clears the field.
    """
    model_config = ConfigDict(extra="forbid")

    first_name: Optional[str] = None
    last_name: Optional[str] = None
    bio: Optional[str] = None
    country: Optional[str] = None
    whatsapp_number: Optional[str] = None


class UpdatePrivacyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_profile_discoverable: Optional[bool] = None
    profile_picture_visibility: Optional[PrivacyScope] = None
    username_visibility: Optional[PrivacyScope] = None
    first_name_visibility: Optional[PrivacyScope] = None
    last_name_visibility: Optional[PrivacyScope] = None
    nickname_visibility: Optional[PrivacyScope] = None
    country_visibility: Optional[PrivacyScope] = None
    phone_number_visibility: Optional[PrivacyScope] = None
    whatsapp_number_visibility: Optional[PrivacyScope] = None
    bio_visibility: Optional[PrivacyScope] = None
    social_links_visibility: Optional[PrivacyScope] = None


class SocialLinkIn(BaseModel):
    platform: str
    url: str
    label: Optional[str] = None


class UpdateSocialLinksRequest(BaseModel):
    links: List[SocialLinkIn] = []
