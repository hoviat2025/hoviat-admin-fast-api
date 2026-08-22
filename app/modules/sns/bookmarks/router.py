from typing import List

from fastapi import APIRouter, Depends, Path

from app.core.schemas import StandardResponse
from app.models.user import User
from app.modules.sns.bookmarks.dependencies import get_bookmark_service
from app.modules.sns.bookmarks.schemas.bookmark import BookmarkActionResponse
from app.modules.sns.bookmarks.services.bookmark_service import BookmarkService
from app.modules.sns.dependencies import get_current_sns_user
from app.modules.sns.profiles.schemas.profile_responses import SingleProfileResponse

router = APIRouter()


@router.get(
    "",
    response_model=StandardResponse[List[SingleProfileResponse]],
    summary="List My Bookmarks",
)
async def list_bookmarks(
    user: User = Depends(get_current_sns_user),
    service: BookmarkService = Depends(get_bookmark_service),
):
    items, total = await service.list(user.user_id)
    return StandardResponse.success(data=items, meta={"total": total})


@router.post(
    "/{user_id}",
    response_model=StandardResponse[BookmarkActionResponse],
    summary="Bookmark a User",
)
async def bookmark_user(
    user_id: int = Path(..., description="The user ID to bookmark"),
    user: User = Depends(get_current_sns_user),
    service: BookmarkService = Depends(get_bookmark_service),
):
    await service.save(user.user_id, user_id)
    return StandardResponse.success(
        data=BookmarkActionResponse(user_id=user_id, bookmarked=True)
    )


@router.delete(
    "/{user_id}",
    response_model=StandardResponse[BookmarkActionResponse],
    summary="Remove a Bookmark",
)
async def unbookmark_user(
    user_id: int = Path(..., description="The user ID to remove from bookmarks"),
    user: User = Depends(get_current_sns_user),
    service: BookmarkService = Depends(get_bookmark_service),
):
    await service.remove(user.user_id, user_id)
    return StandardResponse.success(
        data=BookmarkActionResponse(user_id=user_id, bookmarked=False)
    )
