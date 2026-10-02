from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.services.services.category_service import CategoryService
from app.modules.services.services.service_service import ServiceService


def get_category_service(db: AsyncSession = Depends(get_db)) -> CategoryService:
    """Dependency injection factory for category operations."""
    return CategoryService(db)


def get_service_service(db: AsyncSession = Depends(get_db)) -> ServiceService:
    """Dependency injection factory for service-listing operations."""
    return ServiceService(db)
