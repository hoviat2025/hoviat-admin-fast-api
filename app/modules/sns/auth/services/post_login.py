"""Shared post-authentication steps for all SNS login flows."""

import logging

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.user import User
from app.models.user_privacy_settings import PrivacyScope, UserPrivacySettings
from app.modules.sns.auth.schemas.telegram_login import TelegramLoginResponse
from app.modules.sns.utils import resolve_sync_source

logger = logging.getLogger(__name__)


async def ensure_privacy_row(db: AsyncSession, user_id: int) -> None:
    """
    Create the default privacy row so the profile is discoverable.

    Default policy: nickname, country, profile picture, bio and occupation are
    public; everything else (contact info, names, links) is private. The same
    policy must be kept in sync with:
      - the channel-sync privacy insert (UpdateChannelPostService)
      - migration scripts/database/20260826_11_set_sns_privacy_policy.sql

    Uses ON CONFLICT DO NOTHING so a concurrent insert can never fail this
    login with a unique-violation; an existing row is silently left as-is.
    """
    stmt = (
        pg_insert(UserPrivacySettings)
        .values(
            user_id=user_id,
            is_profile_discoverable=True,
            profile_picture_visibility=PrivacyScope.public.value,
            username_visibility=PrivacyScope.private.value,
            first_name_visibility=PrivacyScope.private.value,
            last_name_visibility=PrivacyScope.private.value,
            nickname_visibility=PrivacyScope.public.value,
            country_visibility=PrivacyScope.public.value,
            phone_number_visibility=PrivacyScope.private.value,
            whatsapp_number_visibility=PrivacyScope.private.value,
            bio_visibility=PrivacyScope.public.value,
            occupation_visibility=PrivacyScope.public.value,
            social_links_visibility=PrivacyScope.private.value,
        )
        .on_conflict_do_nothing(index_elements=[UserPrivacySettings.user_id])
    )
    await db.execute(stmt)
    await db.commit()


async def finalize_login(
    db: AsyncSession,
    queue_repo,
    user: User,
    fallback_first_name: str | None = None,
) -> TelegramLoginResponse:
    """Run privacy, sync, and JWT issuance steps shared by every login flow."""
    await ensure_privacy_row(db, user.user_id)

    try:
        await queue_repo.enqueue_medium_priority(
            user_id=user.user_id,
            source=resolve_sync_source(user),
        )
    except Exception:
        logger.exception(
            "Login succeeded for user %s, but channel sync could not be queued.",
            user.user_id,
        )

    token = create_access_token({"sub": str(user.user_id), "role": "sns_user"})

    # `first_name` is no longer written at login (Telegram names become the
    # nickname); the response's first_name reflects the nickname as a
    # convenience, falling back to what the bot provided.
    return TelegramLoginResponse(
        access_token=token,
        user_id=user.user_id,
        first_name=user.nickname or user.first_name or fallback_first_name or "",
        username=user.username,
    )