from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.schemas import StandardResponse
from app.models.user import User
from app.modules.sns.dependencies import get_current_sns_user
from app.modules.sns.owned_services.schemas import (
    OwnedServiceResponse,
    OwnedServiceUpdateRequest,
)
from app.modules.sns.owned_services.service import OwnedServiceService

router = APIRouter()


def get_owned_service_service(db: AsyncSession = Depends(get_db)):
    return OwnedServiceService(db)


@router.get("", response_model=StandardResponse[list[OwnedServiceResponse]])
async def list_my_services(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_sns_user),
    service: OwnedServiceService = Depends(get_owned_service_service),
):
    items, total = await service.list(user.user_id, page, size)
    return StandardResponse.success(data=items, meta={
        "total": total, "page": page, "size": size,
        "pages": max(1, (total + size - 1) // size),
    })


@router.get("/{service_id}", response_model=StandardResponse[OwnedServiceResponse])
async def get_my_service(
    service_id: int = Path(ge=1),
    user: User = Depends(get_current_sns_user),
    service: OwnedServiceService = Depends(get_owned_service_service),
):
    return StandardResponse.success(data=await service.get(user.user_id, service_id))


@router.patch("/{service_id}", response_model=StandardResponse[OwnedServiceResponse])
async def update_my_service(
    payload: OwnedServiceUpdateRequest,
    service_id: int = Path(ge=1),
    user: User = Depends(get_current_sns_user),
    service: OwnedServiceService = Depends(get_owned_service_service),
):
    return StandardResponse.success(
        data=await service.update(user.user_id, service_id, payload)
    )
