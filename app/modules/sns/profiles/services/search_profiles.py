from typing import List, Tuple

from app.models.user_privacy_settings import PrivacyScope
from app.modules.sns.profiles.repositories.profile_search import ProfileSearchRepository
from app.modules.sns.profiles.schemas.profile_requests import ProfileSearchParams
from app.modules.sns.profiles.schemas.profile_responses import SingleProfileResponse
from app.modules.sns.schemas import SocialLinkResponse


class SearchProfilesService:
    """
    Business logic for searching users and redacting sensitive fields
    before serializing them to the response schema.
    """

    def __init__(self, repo: ProfileSearchRepository):
        self.repo = repo

    async def execute(
        self, params: ProfileSearchParams
    ) -> Tuple[List[SingleProfileResponse], int]:
        # 1. Fetch matching rows from DB.
        users, total = await self.repo.search_profiles(params)

        responses = []

        # 2. Iterate and apply strict field-level redaction.
        for user in users:
            privacy = user.privacy_settings

            # Failsafe check to ensure undiscoverable profiles never leak.
            if not privacy or not privacy.is_profile_discoverable:
                continue

            # Base visible data.
            data = {
                "user_id": user.user_id,
                "is_ban": user.is_ban,
                "is_registered": user.is_registered,
                "join_date": user.join_date,
                "profile_url": None,
            }

            # Map specific fields only if they are explicitly marked as public.
            if privacy.username_visibility == PrivacyScope.public:
                data["username"] = user.username

            if privacy.nickname_visibility == PrivacyScope.public:
                data["nickname"] = user.nickname

            if privacy.first_name_visibility == PrivacyScope.public:
                data["first_name"] = user.first_name

            if privacy.last_name_visibility == PrivacyScope.public:
                data["last_name"] = user.last_name

            if privacy.bio_visibility == PrivacyScope.public:
                data["bio"] = user.bio

            if privacy.phone_number_visibility == PrivacyScope.public:
                data["phone_number"] = user.phone_number

            if privacy.whatsapp_number_visibility == PrivacyScope.public:
                data["whatsapp_number"] = user.whatsapp_number

            if privacy.country_visibility == PrivacyScope.public:
                data["country"] = user.country

            if privacy.profile_picture_visibility == PrivacyScope.public and user.profile_path:
                data["profile_url"] = user.profile_path

            if privacy.social_links_visibility == PrivacyScope.public:
                data["social_links"] = [
                    SocialLinkResponse.model_validate(link) for link in user.social_links
                ]

            responses.append(SingleProfileResponse(**data))

        return responses, total
