from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.user_privacy_settings import PrivacyScope


class UpdateProfileRequest(BaseModel):
    """
    PATCH body for the authenticated user's own profile fields.
    Only supplied fields are updated; a supplied null clears the field.
    """
    model_config = ConfigDict(extra="forbid")

    first_name: Optional[str] = None
    last_name: Optional[str] = None
    nickname: Optional[str] = Field(default=None, min_length=1, max_length=200)
    bio: Optional[str] = None
    occupation: Optional[str] = None
    country: Optional[str] = None
    whatsapp_number: Optional[str] = None

    @field_validator("nickname", mode="before")
    @classmethod
    def public_name(cls, value):
        if value is None or not isinstance(value, str) or not value.strip():
            raise ValueError("Name cannot be blank")
        return value.strip()


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
    occupation_visibility: Optional[PrivacyScope] = None
    social_links_visibility: Optional[PrivacyScope] = None

    @field_validator("*", mode="before")
    @classmethod
    def reject_explicit_null(cls, value):
        # Omitted fields keep their defaults and are excluded from PATCH data.
        # Supplied null cannot be stored in the non-null privacy columns.
        if value is None:
            raise ValueError("Privacy settings cannot be null")
        return value


class SocialLinkIn(BaseModel):
    platform: str
    url: str
    label: Optional[str] = None


class UpdateSocialLinksRequest(BaseModel):
    links: List[SocialLinkIn] = []
