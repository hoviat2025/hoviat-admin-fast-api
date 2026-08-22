from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile

from app.core.schemas import StandardResponse
from app.models.user import User
from app.modules.sns.account.dependencies import (
    get_account_service,
    get_profile_media_service,
)
from app.modules.sns.account.schemas.account_requests import (
    UpdatePrivacyRequest,
    UpdateProfileRequest,
    UpdateSocialLinksRequest,
)
from app.modules.sns.account.schemas.account_responses import (
    OwnProfileResponse,
    ProfilePictureResponse,
)
from app.modules.sns.account.services.account_service import AccountService
from app.modules.sns.account.services.profile_media import ProfileMediaService
from app.modules.sns.dependencies import get_current_sns_user
from app.modules.sns.rate_limit import profile_picture_rate_limit

router = APIRouter()


@router.get(
    "/me",
    response_model=StandardResponse[OwnProfileResponse],
    summary="Get My Profile",
)
async def get_me(
    user: User = Depends(get_current_sns_user),
    service: AccountService = Depends(get_account_service),
):
    result = await service.get_me(user.user_id)
    return StandardResponse.success(data=result)


@router.patch(
    "/profile",
    response_model=StandardResponse[OwnProfileResponse],
    summary="Update My Profile",
)
async def update_profile(
    payload: UpdateProfileRequest,
    user: User = Depends(get_current_sns_user),
    service: AccountService = Depends(get_account_service),
):
    result = await service.update_profile(user.user_id, payload)
    return StandardResponse.success(data=result)


@router.patch(
    "/privacy",
    response_model=StandardResponse[OwnProfileResponse],
    summary="Update Privacy Settings",
)
async def update_privacy(
    payload: UpdatePrivacyRequest,
    user: User = Depends(get_current_sns_user),
    service: AccountService = Depends(get_account_service),
):
    result = await service.update_privacy(user.user_id, payload)
    return StandardResponse.success(data=result)


@router.put(
    "/social-links",
    response_model=StandardResponse[OwnProfileResponse],
    summary="Replace Social Links",
)
async def set_social_links(
    payload: UpdateSocialLinksRequest,
    user: User = Depends(get_current_sns_user),
    service: AccountService = Depends(get_account_service),
):
    result = await service.set_social_links(user.user_id, payload)
    return StandardResponse.success(data=result)


@router.post(
    "/me/profile-picture",
    response_model=StandardResponse[ProfilePictureResponse],
    summary="Upload My Profile Picture",
    dependencies=[Depends(profile_picture_rate_limit)],
)
async def upload_profile_picture(
    file: Annotated[UploadFile, File(description="JPEG, PNG, or WebP image")],
    user: User = Depends(get_current_sns_user),
    service: ProfileMediaService = Depends(get_profile_media_service),
):
    result = await service.replace_avatar(user, file)
    return StandardResponse.success(data=result)


@router.delete(
    "/me/profile-picture",
    response_model=StandardResponse[ProfilePictureResponse],
    summary="Remove My Profile Picture",
)
async def remove_profile_picture(
    user: User = Depends(get_current_sns_user),
    service: ProfileMediaService = Depends(get_profile_media_service),
):
    result = await service.remove_avatar(user)
    return StandardResponse.success(data=result)
