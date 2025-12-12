from fastapi import APIRouter, Depends, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Optional

from app.core.database import get_db
from app.core.schemas import StandardResponse

# --- Schemas ---
from app.modules.eurobot.members.schemas.bot_user_dto import BotUserResponse
from app.modules.eurobot.members.schemas.update_request import BotUpdateMemberRequest
from app.modules.eurobot.members.schemas.bulk_read_request import BulkReadMembersRequest

# --- Services ---
from app.modules.eurobot.members.services.get_member_service import GetMemberService
from app.modules.eurobot.members.services.update_member_service import UpdateMemberService
from app.modules.eurobot.members.services.bulk_read_members_service import BulkReadMembersService
# Import New Service
from app.modules.eurobot.members.services.get_member_by_message_service import GetMemberByMessageService

router = APIRouter()

@router.get("/read_member", response_model=StandardResponse[BotUserResponse])
async def read_member(
    user_id: int = Query(..., description="The User ID to fetch"),
    db: AsyncSession = Depends(get_db)
):
    service = GetMemberService(db)
    user = await service.execute(user_id)
    return StandardResponse.success(data=user)

# --- NEW ENDPOINT ---
@router.get("/member_by_message", response_model=StandardResponse[BotUserResponse])
async def member_by_message(
    public_message_id: int = Query(..., description="The message ID in the public channel"),
    db: AsyncSession = Depends(get_db)
):
    """
    Fetches a user based on their public channel message ID.
    Protected by Bot Token.
    """
    service = GetMemberByMessageService(db)
    user = await service.execute(public_message_id)
    return StandardResponse.success(data=user)
# --------------------

@router.post("/read_bulk_members", response_model=StandardResponse[Dict[str, Optional[BotUserResponse]]])
async def read_bulk_members(
    payload: BulkReadMembersRequest,
    db: AsyncSession = Depends(get_db)
):
    service = BulkReadMembersService(db)
    result_map = await service.execute(payload.user_ids)
    return StandardResponse.success(data=result_map)

@router.put("/update_member", response_model=StandardResponse[BotUserResponse])
async def update_member(
    payload: BotUpdateMemberRequest,
    db: AsyncSession = Depends(get_db)
):
    service = UpdateMemberService(db)
    updated_user = await service.execute(payload)
    return StandardResponse.success(data=updated_user)