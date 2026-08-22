from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.sns.account.services.account_service import AccountService
from app.modules.sns.account.services.profile_media import ProfileMediaService


def get_account_service(db: AsyncSession = Depends(get_db)) -> AccountService:
    """
    Dependency injection factory for the SNS account feature.
    """
    return AccountService(db)


def get_profile_media_service(
    db: AsyncSession = Depends(get_db),
) -> ProfileMediaService:
    """Dependency injection factory for profile-picture operations."""
    return ProfileMediaService(db)
