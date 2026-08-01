from fastapi import HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings


security_scheme = HTTPBearer()


def verify_hilfen_token(
    credentials: HTTPAuthorizationCredentials = Security(security_scheme),
):
    """Validate Hilfen's API bearer token."""

    if credentials.credentials != settings.HILFEN_API_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid Hilfen Bot Token",
        )

    return credentials.credentials
