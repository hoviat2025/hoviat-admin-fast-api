import secrets

from fastapi import Header, HTTPException, status

from app.core.config import settings


async def require_cron_secret(
    cron_secret: str | None = Header(default=None, alias="X-Cron-Secret"),
) -> None:
    """Authorize the internal scheduler without exposing the shared secret."""
    if not cron_secret or not secrets.compare_digest(cron_secret, settings.CRON_SYNC_SECRET):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid cron credentials",
        )
