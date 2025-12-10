from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.schemas import StandardResponse

# Input Schema
from app.modules.eurobot.channels.schemas.update_post_request import UpdateChannelPostRequest
# Service
from app.modules.eurobot.channels.services.update_channel_post_service import UpdateChannelPostService
# Output Schema (Reuse the one from members module)
from app.modules.eurobot.members.schemas.bot_user_dto import BotUserResponse

router = APIRouter()

@router.post("/update_post", response_model=StandardResponse[BotUserResponse])
async def update_post(
    payload: UpdateChannelPostRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Updates the post caption in the main channel for a specific user.
    Returns the updated user object.
    """
    service = UpdateChannelPostService(db)
    
    # Execute returns the User model now
    updated_user = await service.execute(payload)
    
    return StandardResponse.success(data=updated_user)