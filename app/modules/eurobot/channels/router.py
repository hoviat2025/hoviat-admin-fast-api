from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.schemas import StandardResponse

# Input Schema
from app.modules.eurobot.channels.schemas.update_post_request import UpdateChannelPostRequest

# Output Schemas
from app.modules.eurobot.members.schemas.bot_user_dto import BotUserResponse
from app.modules.eurobot.channels.schemas.quote_reply_info_response import QuoteReplyInfoResponse

# Services
from app.modules.eurobot.channels.services.update_channel_post_service import UpdateChannelPostService
from app.modules.eurobot.channels.services.get_quote_reply_info_service import GetQuoteReplyInfoService

router = APIRouter()

@router.post("/update_post", response_model=StandardResponse[BotUserResponse])
async def update_post(
    payload: UpdateChannelPostRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Updates the post caption in the main channel for a specific user.
    """
    service = UpdateChannelPostService(db)
    updated_user = await service.execute(payload)
    return StandardResponse.success(data=updated_user)


@router.get("/quote_reply_info", response_model=StandardResponse[QuoteReplyInfoResponse])
async def get_quote_reply_info(
    user_id: int = Query(..., description="The User ID to fetch info for"),
    db: AsyncSession = Depends(get_db)
):
    """
    Checks sync status, updates if needed, and returns flattened component info + IDs.
    """
    service = GetQuoteReplyInfoService(db)
    
    # execute returns a dict like: 
    # { "id": 5, "some_component_field": "abc", "channel_message_id": 123, ... }
    flattened_data = await service.execute(user_id)
    
    # StandardResponse will wrap this in "data": { ... }
    return StandardResponse.success(data=flattened_data)