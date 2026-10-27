"""Authentication for channel-message mapping callbacks from the sender Worker."""
import hmac

from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings

_bearer = HTTPBearer(auto_error=False)


async def verify_sender_worker(
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer),
) -> None:
    expected = settings.SENDER_WEBHOOK_API_SECRET
    supplied = credentials.credentials if credentials else ""
    if not expected or not supplied or not hmac.compare_digest(
        supplied.encode('utf-8'), expected.encode('utf-8')
    ):
        raise HTTPException(
            status_code=401, detail="Invalid sender worker token",
            headers={"WWW-Authenticate": "Bearer"},
        )
