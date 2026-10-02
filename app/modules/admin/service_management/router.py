from typing import List

from fastapi import APIRouter, Depends, Query, Request

from app.core.schemas import StandardResponse
from app.models.admin import Admin
from app.modules.admin.dependencies import (
    require_read_users_permission,
    require_write_users_permission,
)
from app.modules.admin.service_management.dependencies import (
    get_admin_service_management_service,
)
from app.modules.admin.service_management.services.admin_service_service import (
    AdminServiceManagementService,
)
from app.modules.admin.service_management.schemas.list_services import (
    OwnerAssignRequest,
    ServiceListMeta,
    ServiceListQuery,
)
from app.modules.services.schemas.category_requests import (
    CategoryCreateRequest,
    CategoryUpdateRequest,
)
from app.modules.services.schemas.category_responses import (
    CategoryResponse,
    CategoryTreeResponse,
)
from app.modules.services.schemas.service_requests import (
    ServiceAggregateSaveRequest,
    ServiceCategoriesReplaceRequest,
    ServiceContactsReplaceRequest,
    ServiceCreateRequest,
    ServiceStatusUpdateRequest,
    ServiceUpdateRequest,
)
from app.modules.services.schemas.service_responses import ServiceResponse

router = APIRouter()


def _client(request: Request):
    """Pull client IP and user agent for the audit record, like users_management."""
    return (
        request.client.host if request.client else None,
        request.headers.get("user-agent"),
    )


# =======================================================================
# Services
# =======================================================================


@router.get(
    "/services/",
    response_model=StandardResponse[List[ServiceResponse]],
    summary="List / search services (admin)",
    dependencies=[Depends(require_read_users_permission)],
)
async def list_services(
    query: ServiceListQuery = Depends(),
    service: AdminServiceManagementService = Depends(
        get_admin_service_management_service
    ),
):
    rows, total = await service.list_services(query)
    meta = ServiceListMeta(
        total=total,
        page=query.page,
        size=query.size,
        pages=(total + query.size - 1) // query.size if total > 0 else 1,
    )
    return StandardResponse.success(data=rows, meta=meta.model_dump())


@router.get(
    "/services/{service_id}",
    response_model=StandardResponse[ServiceResponse],
    summary="Get one service (admin)",
    dependencies=[Depends(require_read_users_permission)],
)
async def get_service(
    service_id: int,
    service: AdminServiceManagementService = Depends(
        get_admin_service_management_service
    ),
):
    result = await service.get_service(service_id)
    return StandardResponse.success(data=result)


@router.post(
    "/services/",
    response_model=StandardResponse[ServiceResponse],
    summary="Create a service",
    dependencies=[Depends(require_write_users_permission)],
)
async def create_service(
    payload: ServiceCreateRequest,
    request: Request,
    admin: Admin = Depends(require_write_users_permission),
    service: AdminServiceManagementService = Depends(
        get_admin_service_management_service
    ),
):
    ip, ua = _client(request)
    result = await service.create_service(payload, admin, ip, ua)
    return StandardResponse.success(data=result)


@router.patch(
    "/services/{service_id}",
    response_model=StandardResponse[ServiceResponse],
    summary="Update a service's own fields",
    dependencies=[Depends(require_write_users_permission)],
)
async def update_service(
    service_id: int,
    payload: ServiceUpdateRequest,
    request: Request,
    admin: Admin = Depends(require_write_users_permission),
    service: AdminServiceManagementService = Depends(
        get_admin_service_management_service
    ),
):
    ip, ua = _client(request)
    result = await service.update_service(service_id, payload, admin, ip, ua)
    return StandardResponse.success(data=result)


@router.put(
    "/services/{service_id}",
    response_model=StandardResponse[ServiceResponse],
    summary="Save a service's full editable aggregate atomically",
    description=(
        "Commits own fields, owner, show_owner, contacts and categories in a "
        "single transaction, so a failure can never leave new contacts "
        "attached to old categories. Pass the `updated_at` that was loaded as "
        "`expected_updated_at` to detect a concurrent edit (409)."
    ),
    dependencies=[Depends(require_write_users_permission)],
)
async def save_service(
    service_id: int,
    payload: ServiceAggregateSaveRequest,
    request: Request,
    admin: Admin = Depends(require_write_users_permission),
    service: AdminServiceManagementService = Depends(
        get_admin_service_management_service
    ),
):
    ip, ua = _client(request)
    result = await service.save_service(service_id, payload, admin, ip, ua)
    return StandardResponse.success(data=result)


@router.patch(
    "/services/{service_id}/status",
    response_model=StandardResponse[ServiceResponse],
    summary="Change a service's status",
    dependencies=[Depends(require_write_users_permission)],
)
async def change_service_status(
    service_id: int,
    payload: ServiceStatusUpdateRequest,
    request: Request,
    admin: Admin = Depends(require_write_users_permission),
    service: AdminServiceManagementService = Depends(
        get_admin_service_management_service
    ),
):
    ip, ua = _client(request)
    result = await service.change_status(service_id, payload.status, admin, ip, ua)
    return StandardResponse.success(data=result)


@router.patch(
    "/services/{service_id}/owner",
    response_model=StandardResponse[ServiceResponse],
    summary="Assign or clear a service's owner user",
    dependencies=[Depends(require_write_users_permission)],
)
async def assign_service_owner(
    service_id: int,
    payload: OwnerAssignRequest,
    request: Request,
    admin: Admin = Depends(require_write_users_permission),
    service: AdminServiceManagementService = Depends(
        get_admin_service_management_service
    ),
):
    ip, ua = _client(request)
    result = await service.assign_owner(
        service_id, payload.owner_user_id, admin, ip, ua
    )
    return StandardResponse.success(data=result)


@router.patch(
    "/services/{service_id}/show-owner",
    response_model=StandardResponse[ServiceResponse],
    summary="Toggle whether the owner is shown publicly",
    dependencies=[Depends(require_write_users_permission)],
)
async def set_service_show_owner(
    service_id: int,
    request: Request,
    show_owner: bool = Query(
        ..., description="Whether the owner may be shown publicly"
    ),
    admin: Admin = Depends(require_write_users_permission),
    service: AdminServiceManagementService = Depends(
        get_admin_service_management_service
    ),
):
    ip, ua = _client(request)
    result = await service.set_show_owner(service_id, show_owner, admin, ip, ua)
    return StandardResponse.success(data=result)


@router.put(
    "/services/{service_id}/contacts",
    response_model=StandardResponse[ServiceResponse],
    summary="Replace a service's contact methods",
    dependencies=[Depends(require_write_users_permission)],
)
async def replace_service_contacts(
    service_id: int,
    payload: ServiceContactsReplaceRequest,
    request: Request,
    admin: Admin = Depends(require_write_users_permission),
    service: AdminServiceManagementService = Depends(
        get_admin_service_management_service
    ),
):
    ip, ua = _client(request)
    result = await service.replace_contacts(service_id, payload, admin, ip, ua)
    return StandardResponse.success(data=result)


@router.put(
    "/services/{service_id}/categories",
    response_model=StandardResponse[ServiceResponse],
    summary="Replace a service's category assignments (one primary)",
    dependencies=[Depends(require_write_users_permission)],
)
async def replace_service_categories(
    service_id: int,
    payload: ServiceCategoriesReplaceRequest,
    request: Request,
    admin: Admin = Depends(require_write_users_permission),
    service: AdminServiceManagementService = Depends(
        get_admin_service_management_service
    ),
):
    ip, ua = _client(request)
    result = await service.replace_categories(service_id, payload, admin, ip, ua)
    return StandardResponse.success(data=result)


# =======================================================================
# Categories
# =======================================================================


@router.get(
    "/categories/",
    response_model=StandardResponse[List[CategoryResponse]],
    summary="List categories (admin)",
    dependencies=[Depends(require_read_users_permission)],
)
async def list_categories(
    include_inactive: bool = Query(True),
    service: AdminServiceManagementService = Depends(
        get_admin_service_management_service
    ),
):
    result = await service.list_categories(include_inactive=include_inactive)
    return StandardResponse.success(data=result)


@router.get(
    "/categories/tree",
    response_model=StandardResponse[List[CategoryTreeResponse]],
    summary="Get the category tree (admin)",
    dependencies=[Depends(require_read_users_permission)],
)
async def get_category_tree(
    include_inactive: bool = Query(True),
    service: AdminServiceManagementService = Depends(
        get_admin_service_management_service
    ),
):
    result = await service.get_category_tree(include_inactive=include_inactive)
    return StandardResponse.success(data=result)


@router.post(
    "/categories/",
    response_model=StandardResponse[CategoryResponse],
    summary="Create a category",
    dependencies=[Depends(require_write_users_permission)],
)
async def create_category(
    payload: CategoryCreateRequest,
    request: Request,
    admin: Admin = Depends(require_write_users_permission),
    service: AdminServiceManagementService = Depends(
        get_admin_service_management_service
    ),
):
    ip, ua = _client(request)
    result = await service.create_category(payload, admin, ip, ua)
    return StandardResponse.success(data=result)


@router.patch(
    "/categories/{category_id}",
    response_model=StandardResponse[CategoryResponse],
    summary="Update / move / (de)activate a category",
    dependencies=[Depends(require_write_users_permission)],
)
async def update_category(
    category_id: int,
    payload: CategoryUpdateRequest,
    request: Request,
    admin: Admin = Depends(require_write_users_permission),
    service: AdminServiceManagementService = Depends(
        get_admin_service_management_service
    ),
):
    ip, ua = _client(request)
    result = await service.update_category(category_id, payload, admin, ip, ua)
    return StandardResponse.success(data=result)
