from typing import List
from fastapi import APIRouter, Depends, Query
from fastapi_filter import FilterDepends

# Import StandardResponse
from app.core.schemas import StandardResponse
from app.modules.admin.users_management.schemas.get_user import FullUserResponse
from app.modules.admin.users_management.schemas.update_user import UpdateUserRequest
# Import the new schema for Meta
from app.modules.admin.users_management.schemas.list_users import PaginationMeta
from app.modules.admin.users_management.services.user_service import UserManagementService
from app.modules.admin.users_management.dependencies import get_user_management_service
from app.modules.admin.users_management.filters.user_filter import UserFilter
from app.modules.admin.dependencies import require_read_users_permission, require_write_users_permission

router = APIRouter()

@router.get(
    "/",
    # CRITICAL CHANGE: The Data is now a List of Users. The pagination goes to Meta.
    response_model=StandardResponse[List[FullUserResponse]],
    dependencies=[Depends(require_read_users_permission)]
)
async def list_users(
    user_filter: UserFilter = FilterDepends(UserFilter),
    search: str | None = Query(None, description="Global search across name, email, etc."),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Items per page"),
    service: UserManagementService = Depends(get_user_management_service)
):
    """
    Advanced Search for Users.
    Pagination details are returned in the 'meta' field.
    """
    # 1. Get result from service (contains both items and stats)
    result = await service.list_users(user_filter, search, page, size)
    
    # 2. Extract Data
    items = result["items"]
    
    # 3. Extract Meta using the Pydantic model for validation
    meta_info = PaginationMeta(**result["pagination"])
    
    # 4. Return properly separated response
    return StandardResponse.success(
        data=items, 
        meta=meta_info.model_dump()
    )

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
    result = await service.update_user(payload)
    return StandardResponse.success(result)