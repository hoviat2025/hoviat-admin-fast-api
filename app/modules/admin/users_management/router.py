from fastapi import APIRouter, Depends

# Import StandardResponse
from app.core.schemas import StandardResponse
from app.modules.admin.users_management.schemas.get_user import FullUserResponse
from app.modules.admin.users_management.schemas.update_user import UpdateUserRequest
from app.modules.admin.users_management.services.user_service import UserManagementService
from app.modules.admin.users_management.dependencies import get_user_management_service
from app.modules.admin.dependencies import require_read_users_permission, require_write_users_permission

router = APIRouter()

@router.get(
    "/{user_id}", 
    response_model=StandardResponse[FullUserResponse],
    dependencies=[Depends(require_read_users_permission)]
)
async def get_user_by_telegram_id(
    user_id: int,
    service: UserManagementService = Depends(get_user_management_service)
):
    result = await service.fetch_user_by_id(user_id)
    return StandardResponse.success(result)

@router.patch(
    "/update",
    response_model=StandardResponse[FullUserResponse],
    dependencies=[Depends(require_write_users_permission)]
)
async def update_user_profile(
    payload: UpdateUserRequest,
    service: UserManagementService = Depends(get_user_management_service)
):
    """
    Updates user fields. 
    Only fields sent in the body will be updated.
    Empty strings "" will be converted to null.
    System fields cannot be updated via this endpoint.
    """
    result = await service.update_user(payload)
    return StandardResponse.success(result)