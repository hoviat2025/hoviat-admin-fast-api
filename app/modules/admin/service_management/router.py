from typing import List
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile

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
from app.modules.services.schemas.location_requests import CityCreateRequest

router = APIRouter()


from app.modules.admin.service_management.schemas.import_businesses import BusinessImportBatch, CategoryImportBatch
from app.modules.admin.service_management.services.business_import import BusinessImporter
from app.modules.admin.service_management.services.category_import import CategoryImporter
from app.core.database import get_db
from app.models.service_duplicate_archive import ServiceDuplicateArchive
from app.modules.admin.service_management.schemas.duplicates import DuplicateBatch
from app.modules.admin.service_management.services.duplicates import DuplicateHandler, record_dict
from sqlalchemy import select


@router.get("/duplicates/export", dependencies=[Depends(require_write_users_permission)])
async def export_duplicate_candidates(
    after: int = Query(0, ge=0), size: int = Query(200, ge=1, le=500),
    city: str | None = Query(None, max_length=200), parent_id: int | None = Query(None, gt=0),
    ceiling: int | None = Query(None, ge=0), db=Depends(get_db),
):
    return StandardResponse.success(data=await DuplicateHandler(db).export(after, size, city, parent_id, ceiling))


@router.post("/duplicates/merge", dependencies=[Depends(require_write_users_permission)])
async def handle_duplicates(payload: DuplicateBatch, request: Request,
                            admin: Admin = Depends(require_write_users_permission), db=Depends(get_db)):
    ip, ua = _client(request)
    return StandardResponse.success(data=await DuplicateHandler(db, admin, ip, ua).run(payload))


@router.get("/duplicates/archive", dependencies=[Depends(require_write_users_permission)])
async def list_duplicate_archive(after: int = Query(0, ge=0), db=Depends(get_db)):
    rows = (await db.execute(select(ServiceDuplicateArchive.original_id, ServiceDuplicateArchive.survivor_id,
        ServiceDuplicateArchive.merged_by, ServiceDuplicateArchive.reason, ServiceDuplicateArchive.archived_at)
        .where(ServiceDuplicateArchive.original_id > after).order_by(ServiceDuplicateArchive.original_id).limit(51))).mappings().all()
    return StandardResponse.success(data={"records": [dict(r) for r in rows[:50]],
                                           "next_after": rows[49]["original_id"] if len(rows) > 50 else None})


@router.get("/duplicates/archive/{original_id}", dependencies=[Depends(require_write_users_permission)])
async def get_duplicate_archive(original_id: int, db=Depends(get_db)):
    from app.core.exceptions import ServiceError
    row = await db.get(ServiceDuplicateArchive, original_id)
    if row is None:
        raise ServiceError("NOT_FOUND", "Archived business not found", 404)
    return StandardResponse.success(data=record_dict(row))


@router.post("/imports/businesses", dependencies=[Depends(require_write_users_permission)])
async def import_businesses(
    payload: BusinessImportBatch, request: Request,
    admin: Admin = Depends(require_write_users_permission), db=Depends(get_db),
):
    ip, ua = _client(request)
    result = await BusinessImporter(db, admin, ip, ua).run(payload)
    return StandardResponse.success(data=result)


@router.post("/imports/categories", dependencies=[Depends(require_write_users_permission)])
async def import_categories(
    payload: CategoryImportBatch, request: Request,
    admin: Admin = Depends(require_write_users_permission), db=Depends(get_db),
):
    ip, ua = _client(request)
    result = await CategoryImporter(db, admin, ip, ua).run(payload)
    return StandardResponse.success(data=result)


@router.post("/locations/cities", dependencies=[Depends(require_write_users_permission)])
async def create_location_city(
    payload: CityCreateRequest,
    request: Request,
    admin: Admin = Depends(require_write_users_permission),
    service: AdminServiceManagementService = Depends(get_admin_service_management_service),
):
    ip, ua = _client(request)
    return StandardResponse.success(data=await service.create_city(payload, admin, ip, ua))


def _client(request: Request):
    """Pull client IP and user agent for the audit record, like users_management."""
    return (
        request.client.host if request.client else None,
        request.headers.get("user-agent"),
    )


# =======================================================================
# Services
# =======================================================================


@router.post(
    "/services/{service_id}/cover-image",
    response_model=StandardResponse[ServiceResponse],
    summary="Upload or replace a business cover image",
    dependencies=[Depends(require_write_users_permission)],
)
async def upload_service_cover_image(
    service_id: int,
    request: Request,
    file: UploadFile = File(..., description="JPEG, PNG or WebP, at most 5 MB"),
    expected_updated_at: datetime = Form(...),
    admin: Admin = Depends(require_write_users_permission),
    service: AdminServiceManagementService = Depends(get_admin_service_management_service),
):
    ip, ua = _client(request)
    result = await service.replace_cover_image(service_id, file, expected_updated_at, admin, ip, ua)
    return StandardResponse.success(data=result)


@router.delete(
    "/services/{service_id}/cover-image",
    response_model=StandardResponse[ServiceResponse],
    summary="Remove a business cover image",
    dependencies=[Depends(require_write_users_permission)],
)
async def remove_service_cover_image(
    service_id: int,
    request: Request,
    expected_updated_at: datetime = Query(...),
    admin: Admin = Depends(require_write_users_permission),
    service: AdminServiceManagementService = Depends(get_admin_service_management_service),
):
    ip, ua = _client(request)
    result = await service.remove_cover_image(service_id, expected_updated_at, admin, ip, ua)
    return StandardResponse.success(data=result)


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
