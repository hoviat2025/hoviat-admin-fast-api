from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.schemas import StandardResponse

from app.modules.hilfen.members.schemas.request import HilfenInsertMemberRequest
from app.modules.hilfen.members.schemas.response import HilfenUserResponse
from app.modules.hilfen.members.services.update_member_service import UpdateHilfenMemberService
from app.modules.hilfen.members.schemas.quote_reply_info_response import (
    HilfenQuoteReplyInfoResponse,
)
from app.modules.hilfen.members.services.get_member_by_message_service import GetMemberByHilfenMessageService
from app.modules.hilfen.members.services.get_member_service import GetHilfenMemberService
from app.modules.hilfen.members.services.insert_member_service import InsertHilfenMemberService
from app.modules.hilfen.members.services.upsert_member_service import UpsertHilfenMemberService
from app.modules.hilfen.members.services.get_quote_reply_info_service import (
    GetHilfenQuoteReplyInfoService,
)

router = APIRouter()

@router.get("/read_member", response_model=StandardResponse[HilfenUserResponse])
async def read_member(
    user_id: int = Query(..., description="The Legacy user ID to query"),
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieves user data formatted back into the original legacy structure 
    expected by Hilfen integrations.
    """
    service = GetHilfenMemberService(db)
    user = await service.execute(user_id)
    return StandardResponse.success(data=HilfenUserResponse.from_db_model(user))

@router.post("/upsert_member", response_model=StandardResponse[HilfenUserResponse])
async def upsert_member(
    payload: HilfenInsertMemberRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Inserts or selectively updates user records while ensuring safe merging logic.
    """
    service = UpsertHilfenMemberService(db)
    user = await service.execute(payload)
    return StandardResponse.success(data=HilfenUserResponse.from_db_model(user))

@router.get("/member_by_message", response_model=StandardResponse[HilfenUserResponse])
async def member_by_message(
    hilfen_message_id: int = Query(..., description="The Hilfen channel message ID to look up"),
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieves user data by their Hilfen channel message ID.
    """
    service = GetMemberByHilfenMessageService(db)
    user = await service.execute(hilfen_message_id)
    return StandardResponse.success(data=HilfenUserResponse.from_db_model(user))

@router.post("/insert_member", response_model=StandardResponse[HilfenUserResponse])
async def insert_member(
    payload: HilfenInsertMemberRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Inserts a new user record. Returns 409 if user already exists.
    """
    service = InsertHilfenMemberService(db)
    user = await service.execute(payload)
    return StandardResponse.success(data=HilfenUserResponse.from_db_model(user))

@router.post("/update_member", response_model=StandardResponse[HilfenUserResponse])
async def update_member(
    payload: HilfenInsertMemberRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Updates an existing user record. Returns 404 if user does not exist.
    """
    service = UpdateHilfenMemberService(db)
    user = await service.execute(payload)
    return StandardResponse.success(data=HilfenUserResponse.from_db_model(user))

@router.get(
    "/quote_reply_info",
    response_model=StandardResponse[HilfenQuoteReplyInfoResponse],
)
async def quote_reply_info(
    user_id: int = Query(..., description="The Legacy user ID to query"),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns formatted components and channel/group/public message ids for a hilfen user.
    """
    service = GetHilfenQuoteReplyInfoService(db)
    data = await service.execute(user_id)
    return StandardResponse.success(data=HilfenQuoteReplyInfoResponse(**data))
