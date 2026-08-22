from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models.user import User
from app.shared.repositories.user_base import UserBaseRepository

# Bearer token scheme for the SNS user panel (JWT issued after Telegram login).
security = HTTPBearer()


async def get_current_sns_user(
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

    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
    except JWTError:
        raise credentials_exception

    user_id = payload.get("sub")
    if not user_id or payload.get("role") != "sns_user":
        raise credentials_exception

    user = await UserBaseRepository(db).get_by_id(int(user_id))
    if user is None:
        raise credentials_exception

    if user.is_ban:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is banned",
        )

    return user
