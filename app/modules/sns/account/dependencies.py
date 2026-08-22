from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.sns.account.services.account_service import AccountService


def get_account_service(db: AsyncSession = Depends(get_db)) -> AccountService:
    """
    Dependency injection factory for the SNS account feature.
    """
    return AccountService(db)
