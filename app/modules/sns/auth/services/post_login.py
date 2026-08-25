"""Shared post-authentication steps for all SNS login flows."""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.user import User
from app.models.user_privacy_settings import UserPrivacySettings
from app.modules.sns.auth.schemas.telegram_login import TelegramLoginResponse
from app.modules.sns.utils import resolve_sync_source

logger = logging.getLogger(__name__)


async def ensure_privacy_row(db: AsyncSession, user_id: int) -> None:
    """Create the default privacy row so the profile is discoverable."""
    existing = await db.scalar(
        select(UserPrivacySettings).where(UserPrivacySettings.user_id == user_id)
    )
    if existing is None:
        db.add(UserPrivacySettings(user_id=user_id))
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

    return TelegramLoginResponse(
        access_token=token,
        user_id=user.user_id,
        first_name=user.first_name or fallback_first_name or "",
        username=user.username,
    )
