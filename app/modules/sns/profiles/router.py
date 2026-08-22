from typing import List

from fastapi import APIRouter, Depends, Path

from app.core.schemas import StandardResponse
from app.modules.sns.profiles.dependencies import (
    provide_get_user_service,
    provide_search_profiles_service,
)
from app.modules.sns.profiles.schemas.profile_requests import ProfileSearchParams
from app.modules.sns.profiles.schemas.profile_responses import SingleProfileResponse
from app.modules.sns.profiles.services.get_user_profile import GetUserProfileService
from app.modules.sns.profiles.services.search_profiles import SearchProfilesService
from app.modules.sns.rate_limit import profile_view_rate_limit, search_rate_limit

router = APIRouter()


@router.get(
    "/search",
    response_model=StandardResponse[List[SingleProfileResponse]],
    summary="Search Public User Profiles",
    description="Search for users based on multiple filter criteria. "
    "Automatically excludes data hidden by user privacy settings.",
    dependencies=[Depends(search_rate_limit)],
)
async def search_users(
    params: ProfileSearchParams = Depends(),
    service: SearchProfilesService = Depends(provide_search_profiles_service),
):
    users, total = await service.execute(params)

    meta = {
        "total": total,
        "page": params.page,
        "size": params.size,
        "pages": (total + params.size - 1) // params.size if total > 0 else 1,
    }

    return StandardResponse.success(data=users, meta=meta)


@router.get(
    "/{user_id}",
    response_model=StandardResponse[SingleProfileResponse],
    summary="Get Public User Profile",
    description="Fetches a user's public info based on their privacy settings.",
    dependencies=[Depends(profile_view_rate_limit)],
)
async def get_user_by_id(
    user_id: int = Path(..., description="The user ID to lookup"),
    service: GetUserProfileService = Depends(provide_get_user_service),
):
    result = await service.execute(user_id)
    return StandardResponse.success(data=result)
