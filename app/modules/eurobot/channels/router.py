from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any

from app.core.database import get_db
from app.core.schemas import StandardResponse

# Input Schemas
from app.modules.eurobot.channels.schemas.update_post_request import UpdateChannelPostRequest
from app.modules.eurobot.channels.schemas.set_group_message_request import SetGroupMessageRequest
from app.modules.eurobot.channels.schemas.set_public_message_request import SetPublicMessageRequest
from app.modules.eurobot.channels.schemas.set_hilfen_message_request import SetHilfenMessageRequest
from app.modules.eurobot.channels.schemas.set_admin_message_request import SetAdminMessageRequest

# Output Schemas
from app.modules.eurobot.members.schemas.bot_user_dto import BotUserResponse

# Services
from app.modules.eurobot.channels.services.update_channel_post_service import UpdateChannelPostService
from app.modules.eurobot.channels.services.batch_update_channel_service import BatchUpdateChannelService
from app.modules.eurobot.channels.services.set_group_message_service import SetGroupMessageService
from app.modules.eurobot.channels.services.set_public_message_service import SetPublicMessageService
from app.modules.eurobot.channels.services.set_hilfen_message_service import SetHilfenMessageService
from app.modules.eurobot.channels.services.set_admin_message_service import SetAdminMessageService


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



@telegram_webhook_router.put("/set_hilfen_message_id_test", response_model=StandardResponse[BotUserResponse])
async def set_hilfen_message_id_test(
    payload: SetHilfenMessageRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Finds user by Main Channel Post ID (external_reply) and sets Public Channel IDs.
    Public Access.
    """
    service = SetHilfenMessageService(db)
    updated_user = await service.execute(payload)
    return StandardResponse.success(data=updated_user)


@telegram_webhook_router.put("/set_admin_message_id_test", response_model=StandardResponse[BotUserResponse])
async def set_admin_message_id_test(
    payload: SetAdminMessageRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Finds user by Main Channel Post ID (external_reply) and sets Admin Channel IDs.
    Admin Access.
    """
    service = SetAdminMessageService(db)
    updated_user = await service.execute(payload)
    return StandardResponse.success(data=updated_user)