from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.schemas import StandardResponse

# --- Imports from your Granular Files ---
# Schemas
from app.modules.eurobot.members.schemas.bot_user_dto import BotUserResponse
from app.modules.eurobot.members.schemas.update_request import BotUpdateMemberRequest

# Services
from app.modules.eurobot.members.services.get_member_service import GetMemberService
from app.modules.eurobot.members.services.update_member_service import UpdateMemberService

router = APIRouter()

@router.get("/read_member", response_model=StandardResponse[BotUserResponse])
async def read_member(
    user_id: int = Query(..., description="The User ID to fetch"),
    db: AsyncSession = Depends(get_db)
):
    # We instantiate the specific service class for this action
    service = GetMemberService(db)
    user = await service.execute(user_id)
    return StandardResponse.success(data=user)

@router.put("/update_member", response_model=StandardResponse[BotUserResponse])
async def update_member(
    payload: BotUpdateMemberRequest,
    db: AsyncSession = Depends(get_db)
):
    # We instantiate the specific service class for this action
    service = UpdateMemberService(db)
    updated_user = await service.execute(payload)
    return StandardResponse.success(data=updated_user)