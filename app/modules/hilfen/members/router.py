from fastapi import APIRouter, Depends, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Optional

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
from app.modules.hilfen.members.schemas.bulk_read_request import BulkReadMembersRequest
from app.modules.hilfen.members.schemas.bulk_insert_request import BulkInsertMembersRequest, BulkInsertResultData
from app.modules.hilfen.members.schemas.bulk_update_request import BulkUpdateMembersRequest, BulkUpdateResultData
from app.modules.hilfen.members.schemas.bulk_upsert_request import BulkUpsertMembersRequest, BulkUpsertResultData
from app.modules.hilfen.members.services.bulk_read_members_service import BulkReadMembersService
from app.modules.hilfen.members.services.bulk_insert_members_service import BulkInsertMembersService
from app.modules.hilfen.members.services.bulk_update_members_service import BulkUpdateMembersService
from app.modules.hilfen.members.services.bulk_upsert_members_service import BulkUpsertMembersService

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

@router.post("/read_bulk_members", response_model=StandardResponse[Dict[str, Optional[HilfenUserResponse]]])
async def read_bulk_members(
    payload: BulkReadMembersRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Reads multiple Hilfen members in one request. Returns a map of
    user_id (as string) -> profile, or null for users that do not exist.
    """
    service = BulkReadMembersService(db)
    result_map = await service.execute(payload.user_ids)
    return StandardResponse.success(data=result_map)

@router.post("/insert_bulk_members", response_model=StandardResponse[BulkInsertResultData])
async def insert_bulk_members(
    payload: BulkInsertMembersRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Inserts multiple Hilfen members. Per-item results; max 20 items per
    batch, extras are reported as failed without being processed.
    """
    service = BulkInsertMembersService(db)
    result = await service.execute(payload.users_info)
    meta_stats = {"successful": len(result.successful), "failed": len(result.failed)}
    return StandardResponse.success(data=result, meta=meta_stats)

@router.post("/update_bulk_members", response_model=StandardResponse[BulkUpdateResultData])
async def update_bulk_members(
    payload: BulkUpdateMembersRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Updates multiple Hilfen members. Per-item results; max 20 items per
    batch, extras are reported as failed without being processed.
    """
    service = BulkUpdateMembersService(db)
    result = await service.execute(payload.users_info)
    meta_stats = {"successful": len(result.successful), "failed": len(result.failed)}
    return StandardResponse.success(data=result, meta=meta_stats)

@router.post("/upsert_bulk_members", response_model=StandardResponse[BulkUpsertResultData])
async def upsert_bulk_members(
    payload: BulkUpsertMembersRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Upserts multiple Hilfen members. Per-item results; max 20 items per
    batch, extras are reported as failed without being processed.
    """
    service = BulkUpsertMembersService(db)
    result = await service.execute(payload.users_info)
    meta_stats = {"successful": len(result.successful), "failed": len(result.failed)}
    return StandardResponse.success(data=result, meta=meta_stats)
