from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.admin.service_management.services.admin_service_service import (
    AdminServiceManagementService,
)


def get_admin_service_management_service(
    db: AsyncSession = Depends(get_db),
) -> AdminServiceManagementService:
    """
    Dependency injection factory for admin service-directory management.

    Uses the same get_db session as the request, so the audit row written by the
    service commits together with the change it describes.
    """
    return AdminServiceManagementService(db)
