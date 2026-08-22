import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ServiceError
from app.models.user_privacy_settings import PrivacyScope
from app.shared.repositories.job_queue import JobQueueRepository
from app.modules.sns.account.repositories.account import AccountRepository
from app.modules.sns.account.repositories.privacy import PrivacyRepository
from app.modules.sns.account.repositories.social_links import SocialLinksRepository
from app.modules.sns.account.schemas.account_requests import (
    UpdatePrivacyRequest,
    UpdateProfileRequest,
    UpdateSocialLinksRequest,
)
from app.modules.sns.account.schemas.account_responses import (
    OwnProfileResponse,
    PrivacySettingsResponse,
)
from app.modules.sns.schemas import SocialLinkResponse
from app.modules.sns.utils import assemble_profile_url, resolve_sync_source

logger = logging.getLogger(__name__)

# Profile fields that appear in the Telegram channel post caption. Editing any
# of these should trigger a channel sync; bio/social links do not.
CHANNEL_VISIBLE_FIELDS = frozenset(
    {"first_name", "last_name", "whatsapp_number", "country"}
)


class AccountService:
    """
    Business logic for the authenticated user's own account.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.account_repo = AccountRepository(db)
        self.privacy_repo = PrivacyRepository(db)
        self.social_repo = SocialLinksRepository(db)
        self.queue_repo = JobQueueRepository(db)

    async def get_me(self, user_id: int) -> OwnProfileResponse:
        user = await self.account_repo.get_full(user_id)
        if not user:
            raise ServiceError("USER_NOT_FOUND", "User not found", 404)
        return self._build_own_profile(user)

    async def update_profile(
        self, user_id: int, payload: UpdateProfileRequest
    ) -> OwnProfileResponse:
        data = payload.model_dump(exclude_unset=True)

        if not data:
            return await self.get_me(user_id)

        # Per-field *_updated_at timestamps are owned by the database trigger
        # set_user_field_updated_at(); do not set them from application code.
        user = await self.account_repo.update(user_id, data)
        if not user:
            raise ServiceError("USER_NOT_FOUND", "User not found", 404)
        await self.db.commit()

        if CHANNEL_VISIBLE_FIELDS.intersection(data):
            await self._enqueue_channel_sync(user)

        return await self.get_me(user_id)

    async def update_privacy(
        self, user_id: int, payload: UpdatePrivacyRequest
    ) -> OwnProfileResponse:
        raw = payload.model_dump(exclude_unset=True)

        # Normalize enum members to their string values before writing to the DB.
        data = {
            key: (value.value if isinstance(value, PrivacyScope) else value)
            for key, value in raw.items()
        }

        if data:
            await self.privacy_repo.upsert(user_id, data)
            await self.db.commit()

        return await self.get_me(user_id)

    async def set_social_links(
        self, user_id: int, payload: UpdateSocialLinksRequest
    ) -> OwnProfileResponse:
        links = [link.model_dump() for link in payload.links]
        await self.social_repo.replace(user_id, links)
        await self.db.commit()
        return await self.get_me(user_id)

    async def _enqueue_channel_sync(self, user) -> None:
        """
        Queue a Telegram channel sync after a channel-visible profile change.
        The user data is already committed, so a queue failure must not turn a
        successful edit into a failed request (mirrors eurobot/hilfen services).
        """
        try:
            await self.queue_repo.enqueue_medium_priority(
                user_id=user.user_id,
                source=resolve_sync_source(user),
            )
        except Exception:
            logger.exception(
                "SNS profile update succeeded, but channel sync could not be "
                "queued (user_id=%s)",
                user.user_id,
            )

    def _build_own_profile(self, user) -> OwnProfileResponse:
        privacy = user.privacy_settings

        return OwnProfileResponse(
            user_id=user.user_id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            nickname=user.nickname,
            bio=user.bio,
            occupation=user.occupation,
            phone_number=user.phone_number,
            whatsapp_number=user.whatsapp_number,
            country=user.country,
            profile_url=assemble_profile_url(user.profile_path),
            is_ban=user.is_ban,
            is_registered=user.is_registered,
            join_date=user.join_date,
            social_links=[
                SocialLinkResponse.model_validate(link) for link in user.social_links
            ],
            privacy=PrivacySettingsResponse.model_validate(privacy) if privacy else None,
        )
