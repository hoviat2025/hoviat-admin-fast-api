from app.core.exceptions import ServiceError
from app.models.user_privacy_settings import PrivacyScope
from app.modules.sns.profiles.repositories.user_lookup import UserLookupRepository
from app.modules.sns.profiles.schemas.profile_responses import SingleProfileResponse
from app.modules.sns.schemas import SocialLinkResponse


class GetUserProfileService:
    """
    Business logic for retrieving a single user's public profile.
    Applies strict privacy filtering rules.
    """

    def __init__(self, repo: UserLookupRepository):
        self.repo = repo

    async def execute(self, user_id: int) -> SingleProfileResponse:
        # 1. Fetch from DB.
        user = await self.repo.get_by_id_with_privacy(user_id)

        # 2. Check: User Exists?
        if not user:
            raise ServiceError("USER_NOT_FOUND", "User not found", 404)

        # 3. Check: Global Discovery Toggle.
        privacy = user.privacy_settings
        if not privacy or not privacy.is_profile_discoverable:
            raise ServiceError("USER_NOT_FOUND", "User profile is not accessible", 404)

        # 4. Prepare Data Container.
        data = {
            "user_id": user.user_id,
            "is_ban": user.is_ban,
            "is_registered": user.is_registered,
            "join_date": user.join_date,
            "profile_url": None,
        }

        # 5. Apply Field-Level Privacy Rules.
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

        return SingleProfileResponse(**data)
