"""Explicit local login as an existing user, or the dedicated synthetic account."""

from datetime import datetime, timedelta, timezone
import hashlib
import hmac
from ipaddress import ip_address
from urllib.parse import urlsplit

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError
from jose import jwt

from app.core.config import settings
from app.core.exceptions import ServiceError
from app.models.user import User
from app.modules.sns.auth.schemas.telegram_login import TelegramLoginResponse
from app.modules.sns.auth.services.post_login import ensure_privacy_row

DEV_IDENTITY_MODE = "sns_dev"


def dev_token_secret() -> str:
    # Domain separation prevents a local impersonation token from validating
    # against a deployment that happens to share the normal SNS secret.
    return hmac.new(settings.SECRET_KEY.encode(), b"hoviat-local-dev-login-v1", hashlib.sha256).hexdigest()


def _dev_token(user_id: int) -> str:
    return jwt.encode({
        "sub": str(user_id), "role": "sns_user", "dev_login": True,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    }, dev_token_secret(), algorithm=settings.ALGORITHM)


def _loopback(host: str | None) -> bool:
    if host == "localhost":
        return True
    try:
        return ip_address(host or "").is_loopback
    except ValueError:
        return False


def dev_login_configuration_enabled() -> bool:
    try:
        database = make_url(settings.DATABASE_URL)
        return (
            settings.DEV_LOGIN_ENABLED
            and settings.DISABLE_BACKGROUND_WORKERS
            and settings.DEV_LOGIN_USER_ID < 0
            and database.drivername.startswith("postgresql")
            and _loopback(database.host)
        )
    except (ArgumentError, ValueError, TypeError):
        return False


def _local_origin(origin: str | None) -> bool:
    if origin is None:
        return True
    try:
        parsed = urlsplit(origin)
        # Accessing port also rejects malformed/out-of-range port syntax.
        parsed.port
        return (
            parsed.scheme in {"http", "https"}
            and _loopback(parsed.hostname)
            and parsed.username is None
            and parsed.password is None
            and not (parsed.path or parsed.query or parsed.fragment)
        )
    except ValueError:
        return False


def require_dev_login(request: Request) -> None:
    # Never trust forwarded headers as permission to mint a session. These
    # request checks supplement the disabled-worker and local-database gates.
    if not (
        dev_login_configuration_enabled()
        and request.client is not None
        and _loopback(request.client.host)
        and _loopback(request.url.hostname)
        and _local_origin(request.headers.get("origin"))
    ):
        raise ServiceError("NOT_FOUND", "Not found", 404)


class DevLoginService:
    def __init__(self, db):
        self.db = db

    async def execute(self, user_id: int | None = None) -> TelegramLoginResponse:
        if not dev_login_configuration_enabled():
            raise ServiceError("NOT_FOUND", "Not found", 404)
        try:
            target_id = settings.DEV_LOGIN_USER_ID if user_id is None else user_id
            if target_id == settings.DEV_LOGIN_USER_ID:
                await self.db.execute(
                    pg_insert(User).values(
                        user_id=settings.DEV_LOGIN_USER_ID, mode=DEV_IDENTITY_MODE,
                        nickname="Local developer", is_ban=False,
                        is_registered=False, is_in_eurobot=False, is_in_hilfen_bot=False,
                    ).on_conflict_do_nothing(index_elements=["user_id"])
                )
            user = await self.db.scalar(
                select(User)
                .where(User.user_id == target_id)
                .execution_options(populate_existing=True)
                .with_for_update()
            )
            if user is None:
                raise ServiceError("USER_NOT_FOUND", "No user with this ID exists in the local database", 404)
            if user.is_ban:
                raise ServiceError("FORBIDDEN", "This account is banned", 403)
            if target_id == settings.DEV_LOGIN_USER_ID and (
                user.mode != DEV_IDENTITY_MODE
                or user.is_in_eurobot
                or user.is_in_hilfen_bot
            ):
                raise ServiceError("DEV_IDENTITY_UNAVAILABLE", "Development identity is unavailable", 409)
            # This only creates a missing privacy row. It preserves existing
            # settings and does not enqueue jobs or call any Telegram service.
            await ensure_privacy_row(self.db, user.user_id)
            return TelegramLoginResponse(
                access_token=_dev_token(user.user_id),
                user_id=user.user_id,
                first_name=user.nickname or user.first_name or "Local developer",
                username=user.username,
            )
        except Exception:
            await self.db.rollback()
            raise
