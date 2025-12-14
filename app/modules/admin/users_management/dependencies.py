from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.shared.repositories.user_base import UserBaseRepository
from app.modules.admin.users_management.services.user_service import UserManagementService

# 1. Shared Repo
def get_user_base_repository(db: AsyncSession = Depends(get_db)) -> UserBaseRepository:
    return UserBaseRepository(db)

# 2. Service Injection
def get_user_management_service(
    repo: UserBaseRepository = Depends(get_user_base_repository)
) -> UserManagementService:
    """
    Injects the shared UserRepo into the Admin UserManagementService.
    """
    return UserManagementService(repo)