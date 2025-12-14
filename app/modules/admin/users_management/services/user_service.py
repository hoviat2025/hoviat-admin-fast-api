from fastapi import status
from app.core.exceptions import ServiceError
from app.shared.repositories.user_base import UserBaseRepository
from app.modules.admin.users_management.schemas.get_user import FullUserResponse
from app.modules.admin.users_management.schemas.update_user import UpdateUserRequest

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

    async def update_user(self, payload: UpdateUserRequest) -> FullUserResponse:
        """
        Updates a user based on user_id.
        """
        # 1. Prepare data (Exclude unset fields so we don't overwrite with defaults)
        update_data = payload.model_dump(exclude_unset=True)
        
        # Remove user_id from the update data (it's the matcher, not a value to change)
        if 'user_id' in update_data:
            del update_data['user_id']

        # 2. Call Repository (Executes the SQL, but does not commit yet)
        updated_user = await self.user_repo.update(payload.user_id, update_data)

        # 3. Check Result
        if not updated_user:
            raise ServiceError(
                code="USER_NOT_FOUND",
                message=f"Cannot update: User with ID {payload.user_id} not found.",
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        # 4. COMMIT THE TRANSACTION
        # We access the session through the repo to save the changes permanently.
        await self.user_repo.db.commit()
        
        return updated_user