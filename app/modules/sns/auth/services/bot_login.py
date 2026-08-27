"""Bot-issued login tokens for the SNS website.

Flow:
  1. User starts the SNS bot and taps "Login".
  2. Bot calls POST /auth/bot/request-login with the Telegram identity.
  3. This app mints a random single-use token and returns it to the bot.
  4. Bot shows the token to the user; user pastes it into the website.
  5. Website calls POST /auth/exchange-token and receives the SNS JWT.

Tokens are stored only as SHA-256 digests, expire after LOGIN_TOKEN_TTL_SECONDS,
and are consumed atomically so they can never be redeemed twice.
"""

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ServiceError
from app.models.sns_login_token import SnsLoginToken
from app.shared.repositories.job_queue import JobQueueRepository
from app.shared.repositories.user_base import UserBaseRepository

from app.modules.sns.auth.schemas.bot_login import (
    BotLoginRequest,
    BotLoginResponse,
)
from app.modules.sns.auth.schemas.telegram_login import TelegramLoginResponse
from app.modules.sns.auth.services.post_login import finalize_login

logger = logging.getLogger(__name__)


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


async def _purge_expired(db: AsyncSession) -> None:
    """Best-effort cleanup of stale rows so the table stays small."""
    await db.execute(
        SnsLoginToken.__table__.delete().where(
            SnsLoginToken.expires_at < func.now() - timedelta(days=1),
        )
    )


class RequestBotLoginService:
    """Step 3 of the flow: mint a token for a Telegram identity."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_repo = UserBaseRepository(db)

    async def execute(self, payload: BotLoginRequest) -> BotLoginResponse:
        # The Telegram first/last names are combined into our `nickname` field
        # and are NOT stored as first_name/last_name. Those columns belong to
        # the user's self-managed profile (e.g. set later by the frontend via
        # account/profile update); at login we only persist what Telegram
        # tells us: user_id, nickname, and username when present.
        full_name = " ".join(
            part.strip() for part in (payload.first_name, payload.last_name) if part and part.strip()
        )

        user_data = {"user_id": payload.user_id}
        if full_name:
            user_data["nickname"] = full_name
        if payload.username:
            user_data["username"] = payload.username

        # Upsert now so the exchange step can trust that the user exists.
        await self.user_repo.upsert(user_data)

        raw_token = secrets.token_urlsafe(24)  # exactly 32 URL-safe chars
        ttl = settings.LOGIN_TOKEN_TTL_SECONDS

        await _purge_expired(self.db)
        self.db.add(
            SnsLoginToken(
                user_id=payload.user_id,
                token_hash=_hash_token(raw_token),
                expires_at=datetime.now(timezone.utc) + timedelta(seconds=ttl),
            )
        )
        await self.db.commit()

        logger.info("Issued SNS login token for user %s.", payload.user_id)
        return BotLoginResponse(login_token=raw_token, expires_in=ttl)


class ExchangeTokenService:
    """Step 5 of the flow: trade a valid token for an SNS JWT."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.queue_repo = JobQueueRepository(db)

    async def execute(self, raw_token: str) -> TelegramLoginResponse:
        # Atomic consume: only succeeds if the row is unused and unexpired.
        stmt = (
            update(SnsLoginToken)
            .where(
                SnsLoginToken.token_hash == _hash_token(raw_token),
                SnsLoginToken.used_at.is_(None),
                SnsLoginToken.expires_at > func.now(),
            )
            .values(used_at=func.now())
            .returning(SnsLoginToken.user_id)
        )
        result = await self.db.execute(stmt)
        user_id = result.scalars().first()

        if user_id is None:
            raise ServiceError(
                code="INVALID_LOGIN_TOKEN",
                message="Login token is invalid, expired, or already used.",
                status_code=401,
            )

        # Persist the consumption immediately; get_db never auto-commits.
        await self.db.commit()

        user = await UserBaseRepository(self.db).get_by_id(user_id)
        if user is None:
            await self.db.rollback()
            raise ServiceError(
                code="INVALID_LOGIN_TOKEN",
                message="Login token is invalid, expired, or already used.",
                status_code=401,
            )

        return await finalize_login(self.db, self.queue_repo, user)
