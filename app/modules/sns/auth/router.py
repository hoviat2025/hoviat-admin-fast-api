from fastapi import APIRouter, Depends

from app.core.schemas import StandardResponse
from app.modules.sns.auth.dependencies import get_telegram_login_service
from app.modules.sns.auth.schemas.telegram_login import (
    TelegramLoginRequest,
    TelegramLoginResponse,
)
from app.modules.sns.auth.services.telegram_login import TelegramLoginService
from app.modules.sns.rate_limit import login_rate_limit

router = APIRouter()


@router.post(
    "/telegram",
    response_model=StandardResponse[TelegramLoginResponse],
    summary="Telegram Login Widget",
    description="Validates a Telegram Login Widget payload and issues a JWT.",
    dependencies=[Depends(login_rate_limit)],
)
async def telegram_login(
    payload: TelegramLoginRequest,
    service: TelegramLoginService = Depends(get_telegram_login_service),
):
    result = await service.execute(payload)
    return StandardResponse.success(data=result)
