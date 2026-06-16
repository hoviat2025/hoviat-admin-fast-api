from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.schemas import StandardResponse

from app.modules.hilfen.members.schemas.request import HilfenInsertMemberRequest
from app.modules.hilfen.members.schemas.response import HilfenUserResponse
from app.modules.hilfen.members.services.get_member_service import GetHilfenMemberService
from app.modules.hilfen.members.services.upsert_member_service import UpsertHilfenMemberService

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