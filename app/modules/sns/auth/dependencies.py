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

_bot_bearer = HTTPBearer(auto_error=False)


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


async def verify_login_worker(
    credentials: HTTPAuthorizationCredentials | None = Security(_bot_bearer),
) -> None:
    """
    Authenticates the login-bot Cloudflare worker via the shared
    LOGIN_BOT_API_SECRET sent as a Bearer token.
    """
    supplied = credentials.credentials if credentials else ""

    if not supplied or not hmac.compare_digest(supplied, settings.LOGIN_BOT_API_SECRET):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid worker token",
            headers={"WWW-Authenticate": "Bearer"},
        )
