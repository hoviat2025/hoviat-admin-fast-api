import hashlib
import hmac
import logging
import time

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ServiceError
from app.shared.repositories.job_queue import JobQueueRepository
from app.shared.repositories.user_base import UserBaseRepository

from app.modules.sns.auth.schemas.telegram_login import (
    TelegramLoginRequest,
    TelegramLoginResponse,
)
from app.modules.sns.auth.services.post_login import finalize_login

logger = logging.getLogger(__name__)


def _verify_telegram_hash(data: dict, bot_token: str) -> bool:
    """
    Validate the Telegram Login Widget signature.

    data_check_string = sorted "key=value" lines (excluding hash)
    secret_key = SHA256(bot_token)
    hash = HMAC-SHA256(secret_key, data_check_string)
    """
    received_hash = data.get("hash")
    if not received_hash:
        return False

    data_check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(data.items()) if k != "hash"
    )
    secret_key = hashlib.sha256(bot_token.encode("utf-8")).digest()
    computed_hash = hmac.new(
        secret_key,
        data_check_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(computed_hash, received_hash)


class TelegramLoginService:
    """
    Validates a Telegram login, upserts the user, and issues a JWT.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_repo = UserBaseRepository(db)
        self.queue_repo = JobQueueRepository(db)

    async def execute(self, payload: TelegramLoginRequest) -> TelegramLoginResponse:
        bot_token = settings.SNS_BOT_TOKEN or settings.BOT_API_TOKEN

        # 1. Verify the widget signature.
        if not _verify_telegram_hash(payload.model_dump(exclude_none=True), bot_token):
            raise ServiceError(
                code="INVALID_TELEGRAM_AUTH",
                message="Telegram authentication failed.",
                status_code=401,
            )

        # 2. Reject stale auth attempts.
        if time.time() - payload.auth_date > settings.TELEGRAM_LOGIN_MAX_AGE_SECONDS:
            raise ServiceError(
                code="AUTH_EXPIRED",
                message="Telegram authentication has expired.",
                status_code=401,
            )

        # 3. Upsert the Telegram identity.
        user_data = {"user_id": payload.id, "first_name": payload.first_name}
        if payload.username:
            user_data["username"] = payload.username
        if payload.last_name:
            user_data["last_name"] = payload.last_name

        user = await self.user_repo.upsert(user_data)

        # 4-6. Privacy row, channel sync, and JWT issuance are shared.
        return await finalize_login(
            self.db,
            self.queue_repo,
            user,
            fallback_first_name=payload.first_name,
        )
