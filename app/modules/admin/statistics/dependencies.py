from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.admin.statistics.repository import AdminStatisticsRepository


def get_admin_statistics_repository(
    db: AsyncSession = Depends(get_db),
) -> AdminStatisticsRepository:
    return AdminStatisticsRepository(db)
