from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel

from app.core.schemas import StandardResponse
from app.models.user import User
from app.modules.services.schemas.public_service_responses import PublicServiceResponse
from app.modules.sns.dependencies import get_current_sns_user
from app.modules.sns.service_bookmarks.dependencies import get_service_bookmark_service
from app.modules.sns.service_bookmarks.service import ServiceBookmarkService

router = APIRouter()


class ServiceBookmarkActionResponse(BaseModel):
    service_id: int
    bookmarked: bool


@router.get(
    "",
    response_model=StandardResponse[list[PublicServiceResponse]],
    summary="List My Saved Businesses",
)
async def list_service_bookmarks(
    user: User = Depends(get_current_sns_user),
    service: ServiceBookmarkService = Depends(get_service_bookmark_service),
):
    items, total = await service.list(user.user_id)
    return StandardResponse.success(data=items, meta={"total": total})


@router.post(
    "/{service_id}",
    response_model=StandardResponse[ServiceBookmarkActionResponse],
    summary="Save a Business",
)
async def bookmark_service(
    service_id: int = Path(..., gt=0),
    user: User = Depends(get_current_sns_user),
    service: ServiceBookmarkService = Depends(get_service_bookmark_service),
):
    await service.save(user.user_id, service_id)
    return StandardResponse.success(
        data=ServiceBookmarkActionResponse(service_id=service_id, bookmarked=True)
    )


@router.delete(
    "/{service_id}",
    response_model=StandardResponse[ServiceBookmarkActionResponse],
    summary="Remove a Saved Business",
)
async def unbookmark_service(
    service_id: int = Path(..., gt=0),
    user: User = Depends(get_current_sns_user),
    service: ServiceBookmarkService = Depends(get_service_bookmark_service),
):
    await service.remove(user.user_id, service_id)
    return StandardResponse.success(
        data=ServiceBookmarkActionResponse(service_id=service_id, bookmarked=False)
    )
