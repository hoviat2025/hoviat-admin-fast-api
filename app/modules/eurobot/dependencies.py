from fastapi import Security, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.config import settings

# This expects "Authorization: Bearer <token>" header
security_scheme = HTTPBearer()

def verify_bot_token(credentials: HTTPAuthorizationCredentials = Security(security_scheme)):
    """
    Validates that the token matches the BOT_API_TOKEN in .env
    """
    token = credentials.credentials
    if token != settings.BOT_API_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid Bot Token"
        )
    return token