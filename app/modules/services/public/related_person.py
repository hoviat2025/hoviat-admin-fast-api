"""Related-person read boundary: staff permission AND assignment consent AND privacy."""

from typing import Optional
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core.exceptions import ServiceError
from app.models.service import Service, ServiceStatus
from app.modules.sns.profiles.repositories.user_lookup import UserLookupRepository
from app.modules.sns.profiles.services.get_user_profile import GetUserProfileService
from app.modules.sns.schemas import SocialLinkResponse


class RelatedPersonResponse(BaseModel):
    user_id: int
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    nickname: Optional[str] = None
    username: Optional[str] = None
    bio: Optional[str] = None
    profile_url: Optional[str] = None
    social_links: list[SocialLinkResponse] = Field(default_factory=list)


async def related_person(db, service_id: int) -> RelatedPersonResponse | None:
    row = (await db.execute(select(
        Service.owner_user_id, Service.show_owner, Service.owner_show_profile,
    ).where(Service.id == service_id, Service.status == ServiceStatus.published))).first()
    if row is None:
        raise ServiceError("SERVICE_NOT_FOUND", "Service not found", 404)
    if row.owner_user_id is None or not row.show_owner or not row.owner_show_profile:
        return None
    # Reuse the existing field-by-field privacy projection; the business
    # association grants no additional access to private personal information.
    try:
        profile = await GetUserProfileService(UserLookupRepository(db)).execute(row.owner_user_id)
    except ServiceError as error:
        if error.status_code == 404:
            return None
        raise
    if profile.is_ban:
        return None
    data = profile.model_dump(include=set(RelatedPersonResponse.model_fields))
    data["social_links"] = [link for link in data.get("social_links") or []
                            if link["platform"].lower() in {"telegram", "whatsapp", "phone", "linkedin",
                                                            "instagram", "twitter", "x", "bluesky", "discord"}]
    return RelatedPersonResponse.model_validate(data)
