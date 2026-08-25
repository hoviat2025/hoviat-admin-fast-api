from fastapi import APIRouter, Depends

from app.core.schemas import StandardResponse
from app.modules.sns.auth.dependencies import (
    get_exchange_token_service,
    get_request_bot_login_service,
    verify_login_worker,
)
from app.modules.sns.auth.schemas.bot_login import (
    BotLoginRequest,
    BotLoginResponse,
    TokenExchangeRequest,
)
from app.modules.sns.auth.schemas.telegram_login import TelegramLoginResponse
from app.modules.sns.rate_limit import login_rate_limit

router = APIRouter()


@router.post(
    "/bot/request-login",
    response_model=StandardResponse[BotLoginResponse],
    summary="Bot: mint a login token",
    description=(
        "Called by the SNS bot worker when a user asks to log in. Mints a "
        "short-lived single-use token that the user pastes into the website."
    ),
    dependencies=[Depends(verify_login_worker)],
)
async def bot_request_login(
    payload: BotLoginRequest,
    service=Depends(get_request_bot_login_service),
):
    result = await service.execute(payload)
    return StandardResponse.success(data=result)


@router.post(
    "/exchange-token",
    response_model=StandardResponse[TelegramLoginResponse],
    summary="Exchange login token for JWT",
    description=(
        "Called by the website with the token the user received from the bot. "
        "Consumes the token and returns the standard SNS session."
    ),
    dependencies=[Depends(login_rate_limit)],
)
async def exchange_token(
    payload: TokenExchangeRequest,
    service=Depends(get_exchange_token_service),
):
    result = await service.execute(payload.token)
    return StandardResponse.success(data=result)
