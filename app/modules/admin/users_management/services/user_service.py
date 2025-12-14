from fastapi import status
from typing import Dict, Any

from app.core.exceptions import ServiceError
from app.shared.repositories.user_base import UserBaseRepository
from app.modules.admin.users_management.schemas.get_user import FullUserResponse
from app.modules.admin.users_management.schemas.update_user import UpdateUserRequest
from app.modules.admin.users_management.repositories.user_search import UserSearchRepository
from app.modules.admin.users_management.filters.user_filter import UserFilter

class UserManagementService:
    def __init__(self, user_repo: UserSearchRepository):
        self.user_repo = user_repo

    async def fetch_user_by_id(self, user_id: int) -> FullUserResponse:
        user = await self.user_repo.get_by_id(user_id)
        
        if not user:
            raise ServiceError(
                code="USER_NOT_FOUND",
                message=f"User with ID {user_id} not found.",
                status_code=status.HTTP_404_NOT_FOUND
            )
            
        return user

    async def update_user(self, payload: UpdateUserRequest) -> FullUserResponse:
        """
        Updates a user based on user_id.
        """
        # 1. Prepare data
        update_data = payload.model_dump(exclude_unset=True)
        
        if 'user_id' in update_data:
            del update_data['user_id']

        # 2. Update
        updated_user = await self.user_repo.update(payload.user_id, update_data)

        # 3. Check
        if not updated_user:
            raise ServiceError(
                code="USER_NOT_FOUND",
                message=f"Cannot update: User with ID {payload.user_id} not found.",
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        # 4. Commit
        await self.user_repo.db.commit()
        
        return updated_user
    
    async def list_users(
        self, 
        user_filter: UserFilter, 
        search: str | None, 
        page: int, 
        size: int
    ) -> Dict[str, Any]:
        """
        Returns a dictionary containing the items and pagination stats.
        The Router will be responsible for splitting this into 'data' and 'meta'.
        """
        users, total = await self.user_repo.search_users(
            user_filter=user_filter,
            search_query=search,
            page=page,
            page_size=size
        )
        
        return {
            "items": users,
            "pagination": {
                "total": total,
                "page": page,
                "size": size,
                "pages": (total + size - 1) // size 
            }
        }