from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.schemas import StandardResponse
from app.modules.admin.audit.dependencies import get_admin_audit_repository
from app.modules.admin.audit.repository import AdminAuditRepository
from app.modules.admin.audit.schemas import AuditLogList, AuditLogResponse, AuditPaginationMeta
from app.modules.admin.dependencies import require_read_users_permission

router = APIRouter()


@router.get(
    "/",
    response_model=StandardResponse[AuditLogList],
    dependencies=[Depends(require_read_users_permission)],
)
async def list_audit_logs(
    admin_id: int | None = Query(None, ge=1),
    admin_username: str | None = Query(None),
    target_user_id: int | None = Query(None),
    action: str | None = Query(None),
    changed_field: str | None = Query(None),
    created_after: datetime | None = Query(None),
    created_before: datetime | None = Query(None),
    sync_channels: bool | None = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    repository: AdminAuditRepository = Depends(get_admin_audit_repository),
):
    logs, total = await repository.list_logs(
        page=page,
        size=size,
        admin_id=admin_id,
        admin_username=admin_username,
        target_user_id=target_user_id,
        action=action,
        changed_field=changed_field,
        created_after=created_after,
        created_before=created_before,
        sync_channels=sync_channels,
    )
    meta = AuditPaginationMeta(
        total=total,
        page=page,
        size=size,
        pages=(total + size - 1) // size,
    )
    return StandardResponse.success(data=logs, meta=meta.model_dump())


@router.get(
    "/{audit_id}",
    response_model=StandardResponse[AuditLogResponse],
    dependencies=[Depends(require_read_users_permission)],
)
async def get_audit_log(
    audit_id: int,
    repository: AdminAuditRepository = Depends(get_admin_audit_repository),
):
    audit_log = await repository.get_by_id(audit_id)
    if audit_log is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audit log not found",
        )
    return StandardResponse.success(data=audit_log)
