from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.admin.audit.repository import AdminAuditRepository


def get_admin_audit_repository(
    db: AsyncSession = Depends(get_db),
) -> AdminAuditRepository:
    return AdminAuditRepository(db)
