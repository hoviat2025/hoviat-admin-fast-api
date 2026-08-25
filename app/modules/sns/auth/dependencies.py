import hmac

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.modules.sns.auth.services.bot_login import (
    ExchangeTokenService,
    RequestBotLoginService,
)
from app.modules.sns.auth.services.telegram_login import TelegramLoginService

_bot_bearer = HTTPBearer(auto_error=False)


def get_telegram_login_service(
    db: AsyncSession = Depends(get_db),
) -> TelegramLoginService:
    """
    Dependency injection factory for the Telegram login feature.
    """
    return TelegramLoginService(db)


def get_request_bot_login_service(
    db: AsyncSession = Depends(get_db),
) -> RequestBotLoginService:
    """Dependency injection factory for the bot login-request feature."""
    return RequestBotLoginService(db)


def get_exchange_token_service(
    db: AsyncSession = Depends(get_db),
) -> ExchangeTokenService:
    """Dependency injection factory for the token exchange feature."""
    return ExchangeTokenService(db)


async def verify_sns_bot(
    credentials: HTTPAuthorizationCredentials | None = Security(_bot_bearer),
) -> None:
    """
    Authenticates the SNS bot itself (not a user) via its bot token as Bearer.
    Accepts SNS_BOT_TOKEN with fallback to BOT_API_TOKEN.
    """
    expected = settings.SNS_BOT_TOKEN or settings.BOT_API_TOKEN
    supplied = credentials.credentials if credentials else ""

    if not supplied or not hmac.compare_digest(supplied, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid bot token",
            headers={"WWW-Authenticate": "Bearer"},
        )
