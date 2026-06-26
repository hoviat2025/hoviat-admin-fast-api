from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.schemas import StandardResponse
from app.modules.eurobot.channels.services.set_hilfen_message_service import SetHilfenMessageService
from app.modules.eurobot.channels.schemas.set_hilfen_message_request import SetHilfenMessageRequest

router = APIRouter()

@router.put("/set_hilfen_message_id", response_model=StandardResponse[dict])
async def set_hilfen_message_id(
    payload: SetHilfenMessageRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Public webhook endpoint triggered by Telegram comments in the Hilfen group.
    Stores message IDs in the staging table and updates the main User table when complete.
    """
    service = SetHilfenMessageService(db)
    user = await service.execute(payload)
    return StandardResponse.success(data={"status": "completed", "user_id": user.user_id})