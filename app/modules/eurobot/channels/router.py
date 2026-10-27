from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any

from app.core.database import get_db
from app.core.schemas import StandardResponse
from app.shared.sender_webhook_auth import verify_sender_worker

# Input Schemas
from app.modules.eurobot.channels.schemas.update_post_request import UpdateChannelPostRequest
from app.modules.eurobot.channels.schemas.set_group_message_request import SetGroupMessageRequest
# Import NEW Schema
from app.modules.eurobot.channels.schemas.set_public_message_request import SetPublicMessageRequest

# Output Schemas
from app.modules.eurobot.members.schemas.bot_user_dto import BotUserResponse

# Services
from app.modules.eurobot.channels.services.update_channel_post_service import UpdateChannelPostService
from app.modules.eurobot.channels.services.set_group_message_service import SetGroupMessageService
# Import NEW Service
from app.modules.eurobot.channels.services.set_public_message_service import SetPublicMessageService


# 1. Protected Router
router = APIRouter()

# 2. Webhook Router (historically public; now authenticates the sender Worker).
# `_test` is a historical route name also used in production. The API hostname,
# not this suffix, determines which deployment/database receives the callback.
telegram_webhook_router = APIRouter(dependencies=[Depends(verify_sender_worker)])


# --- PROTECTED ENDPOINTS ---
@router.post("/update_post", response_model=StandardResponse[BotUserResponse])
async def update_post(
    payload: UpdateChannelPostRequest,
    db: AsyncSession = Depends(get_db)
):
    service = UpdateChannelPostService(db)
    updated_user = await service.execute(payload)
    return StandardResponse.success(data=updated_user)


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
    Requires the sender Worker's shared API secret.
    """
    service = SetPublicMessageService(db)
    updated_user = await service.execute(payload)
    return StandardResponse.success(data=updated_user)
