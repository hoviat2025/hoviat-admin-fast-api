from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any

from app.core.database import get_db
from app.core.schemas import StandardResponse

# Input Schemas
from app.modules.eurobot.channels.schemas.update_post_request import UpdateChannelPostRequest
from app.modules.eurobot.channels.schemas.set_group_message_request import SetGroupMessageRequest
# Import NEW Schema
from app.modules.eurobot.channels.schemas.set_public_message_request import SetPublicMessageRequest

# Output Schemas
from app.modules.eurobot.members.schemas.bot_user_dto import BotUserResponse
from app.modules.eurobot.channels.schemas.quote_reply_info_response import QuoteReplyInfoResponse

# Services
from app.modules.eurobot.channels.services.update_channel_post_service import UpdateChannelPostService
from app.modules.eurobot.channels.services.get_quote_reply_info_service import GetQuoteReplyInfoService
from app.modules.eurobot.channels.services.batch_update_channel_service import BatchUpdateChannelService
from app.modules.eurobot.channels.services.set_group_message_service import SetGroupMessageService
# Import NEW Service
from app.modules.eurobot.channels.services.set_public_message_service import SetPublicMessageService


# 1. Protected Router
router = APIRouter()

# 2. Webhook Router (Public)
telegram_webhook_router = APIRouter()


# --- PROTECTED ENDPOINTS ---
@router.post("/update_post", response_model=StandardResponse[BotUserResponse])
async def update_post(
    payload: UpdateChannelPostRequest,
    db: AsyncSession = Depends(get_db)
):
    service = UpdateChannelPostService(db)
    updated_user = await service.execute(payload)
    return StandardResponse.success(data=updated_user)

@router.get("/quote_reply_info", response_model=StandardResponse[QuoteReplyInfoResponse])
async def get_quote_reply_info(
    user_id: int = Query(..., description="The User ID to fetch info for"),
    db: AsyncSession = Depends(get_db)
):
    service = GetQuoteReplyInfoService(db)
    flattened_data = await service.execute(user_id)
    return StandardResponse.success(data=flattened_data)

@router.post("/batch_sync_posts", response_model=StandardResponse[Dict[str, Any]])
async def batch_sync_posts(
    limit: int = Query(25, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    service = BatchUpdateChannelService(db)
    report = await service.execute(limit=limit)
    return StandardResponse.success(data=report)


# --- WEBHOOK ENDPOINTS ---

@telegram_webhook_router.put("/set_group_message_id_test", response_model=StandardResponse[BotUserResponse])
async def set_group_message_id_test(
    payload: SetGroupMessageRequest,
    db: AsyncSession = Depends(get_db)
):
    service = SetGroupMessageService(db)
    updated_user = await service.execute(payload)
    return StandardResponse.success(data=updated_user)

# --- NEW ENDPOINT HERE ---
@telegram_webhook_router.put("/set_public_message_id_test", response_model=StandardResponse[BotUserResponse])
async def set_public_message_id_test(
    payload: SetPublicMessageRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Finds user by Main Channel Post ID (external_reply) and sets Public Channel IDs.
    Public Access.
    """
    service = SetPublicMessageService(db)
    updated_user = await service.execute(payload)
    return StandardResponse.success(data=updated_user)