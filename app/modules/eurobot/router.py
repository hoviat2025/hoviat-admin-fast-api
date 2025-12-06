from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.eurobot.dependencies import verify_bot_token
from app.modules.eurobot.schemas import BotUserResponse, BotUpdateMemberRequest
from app.modules.eurobot.service import EurobotService
from app.core.schemas import StandardResponse

router = APIRouter(dependencies=[Depends(verify_bot_token)])

# The response_model wraps your data in the "data" key automatically
@router.put("/update_member", response_model=StandardResponse[BotUserResponse])
async def update_member(
    payload: BotUpdateMemberRequest,
    db: AsyncSession = Depends(get_db)
):
    service = EurobotService(db)
    updated_user = await service.update_member(payload)
    
    # .success() creates { data: updated_user, meta: {}, error: {} }
    return StandardResponse.success(data=updated_user)