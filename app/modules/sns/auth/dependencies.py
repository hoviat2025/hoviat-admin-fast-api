from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.sns.auth.services.telegram_login import TelegramLoginService


def get_telegram_login_service(
    db: AsyncSession = Depends(get_db),
) -> TelegramLoginService:
    """
    Dependency injection factory for the Telegram login feature.
    """
    return TelegramLoginService(db)
