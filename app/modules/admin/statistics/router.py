from fastapi import APIRouter, Depends

from app.core.schemas import StandardResponse
from app.modules.admin.dependencies import require_read_users_permission
from app.modules.admin.statistics.dependencies import get_admin_statistics_repository
from app.modules.admin.statistics.repository import AdminStatisticsRepository
from app.modules.admin.statistics.schemas import AdminStatisticsResponse


router = APIRouter()


@router.get(
    "/",
    response_model=StandardResponse[AdminStatisticsResponse],
    dependencies=[Depends(require_read_users_permission)],
)
async def get_statistics(
    repository: AdminStatisticsRepository = Depends(get_admin_statistics_repository),
) -> StandardResponse[AdminStatisticsResponse]:
    return StandardResponse.success(await repository.get_statistics())
