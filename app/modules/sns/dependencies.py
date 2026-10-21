from fastapi import Depends, HTTPException, Security, status, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import ServiceError
from app.models.user import User
from app.shared.repositories.user_base import UserBaseRepository
from app.modules.sns.auth.services.dev_login import (
    DEV_IDENTITY_MODE,
    dev_login_configuration_enabled,
    require_dev_login,
    dev_token_secret,
)

# Bearer token scheme for the SNS user panel (JWT issued after Telegram login).
security = HTTPBearer()


async def get_current_sns_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Security(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Validates the SNS user JWT and returns the matching, non-banned User.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    dev_token = False
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
    except JWTError:
        try:
            require_dev_login(request)
            payload = jwt.decode(credentials.credentials, dev_token_secret(), algorithms=[settings.ALGORITHM])
            dev_token = True
        except (JWTError, ServiceError):
            raise credentials_exception

    if dev_token != (payload.get("dev_login") is True):
        raise credentials_exception

    user_id = payload.get("sub")
    if not user_id or payload.get("role") != "sns_user":
        raise credentials_exception

    # All impersonation tokens are explicitly marked, even when the target is
    # a real local user. Disabling dev login invalidates them; they never work
    # on a remote API or with background workers enabled.
    if payload.get("dev_login") is True:
        try:
            require_dev_login(request)
        except ServiceError:
            raise credentials_exception

    try:
        numeric_user_id = int(user_id)
        if not -(2**63) <= numeric_user_id <= 2**63 - 1:
            raise ValueError("Invalid user ID")
    except (ValueError, TypeError, OverflowError):
        raise credentials_exception
    user = await UserBaseRepository(db).get_by_id(numeric_user_id)
    if user is None:
        raise credentials_exception

    # Turning off local login also disables tokens already issued to the
    # synthetic identity. Normal SNS sessions retain their existing behavior.
    if user.mode == DEV_IDENTITY_MODE and not dev_login_configuration_enabled():
        raise credentials_exception

    if user.is_ban:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is banned",
        )

    return user
