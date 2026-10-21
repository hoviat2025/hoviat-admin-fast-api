from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.schemas import StandardResponse
from app.modules.sns.auth.dependencies import (
    get_exchange_token_service,
    get_request_bot_login_service,
    get_dev_login_service,
    verify_login_worker,
)
from app.modules.sns.auth.schemas.bot_login import (
    BotLoginRequest,
    BotLoginResponse,
    TokenExchangeRequest,
)
from app.modules.sns.auth.schemas.telegram_login import TelegramLoginResponse
from app.modules.sns.rate_limit import login_rate_limit
from app.modules.sns.auth.services.dev_login import require_dev_login

router = APIRouter()


class DevLoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: int | None = Field(default=None, ge=-(2**63), le=2**63 - 1)

    @field_validator("user_id", mode="before")
    @classmethod
    def exact_user_id(cls, value):
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, (int, str)):
            raise ValueError("User ID must be an integer")
        if isinstance(value, str):
            import re
            if not re.fullmatch(r"-?[0-9]{1,19}", value):
                raise ValueError("User ID must be an integer")
        return int(value)


class DevLoginCapability(BaseModel):
    enabled: bool


@router.get(
    "/dev-login",
    response_model=StandardResponse[DevLoginCapability],
    dependencies=[Depends(require_dev_login)],
)
async def dev_login_capability():
    return StandardResponse.success(data=DevLoginCapability(enabled=True))


@router.post(
    "/dev-login",
    response_model=StandardResponse[TelegramLoginResponse],
    dependencies=[Depends(require_dev_login), Depends(login_rate_limit)],
)
async def dev_login(
    payload: DevLoginRequest | None = None,
    service=Depends(get_dev_login_service),
):
    return StandardResponse.success(data=await service.execute(payload.user_id if payload else None))


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
