from fastapi import status
# Import ServiceError
from app.core.exceptions import ServiceError
from app.shared.repositories.user_base import UserBaseRepository
from app.modules.admin.users_management.schemas.get_user import FullUserResponse

class UserManagementService:
    def __init__(self, user_repo: UserBaseRepository):
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