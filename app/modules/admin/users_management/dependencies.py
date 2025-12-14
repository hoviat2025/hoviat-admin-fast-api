from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
# 1. Import the new Search Repository
from app.modules.admin.users_management.repositories.user_search import UserSearchRepository
from app.modules.admin.users_management.services.user_service import UserManagementService

# 2. Define the Dependency for the Search Repo
def get_user_search_repository(db: AsyncSession = Depends(get_db)) -> UserSearchRepository:
    """
    Creates an instance of UserSearchRepository.
    This repo has all the Base methods (get, update) PLUS the new search_users method.
    """
    return UserSearchRepository(db)

# 3. Service Injection
def get_user_management_service(
    # CRITICAL FIX: We inject UserSearchRepository here, not UserBaseRepository
    repo: UserSearchRepository = Depends(get_user_search_repository)
) -> UserManagementService:
    """
    Injects the Search Repo into the Admin UserManagementService.
    """
    return UserManagementService(repo)