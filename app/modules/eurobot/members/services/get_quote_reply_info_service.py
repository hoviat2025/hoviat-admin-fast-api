import httpx
import logging
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.encoders import jsonable_encoder

# Core & Config
from app.core.config import settings
from app.core.exceptions import ServiceError
from app.models.user import User
from app.shared.repositories.user_base import UserBaseRepository

# Dependency Service & Request
from app.modules.eurobot.channels.services.update_channel_post_service import UpdateChannelPostService
from app.modules.eurobot.channels.schemas.update_post_request import UpdateChannelPostRequest

logger = logging.getLogger(__name__)

class GetQuoteReplyInfoService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = UserBaseRepository(db)

    async def execute(self, user_id: int) -> Dict[str, Any]:
        """
        1. Syncs User with Channel if needed.
        2. Fetches 'components' from formatter.
        3. Returns a flattened dictionary containing components + ID fields.
        """
        # 1. Get User
        user = await self.repo.get_by_id(user_id)
        if not user:
            raise ServiceError(
                code="USER_NOT_FOUND",
                message=f"User {user_id} not found",
                status_code=404
            )

        # 2. Check Conditions for Update
        should_update = False
        
        if not user.telegram_message_id:
            should_update = True
        elif user.channel_updated_at is None:
            should_update = True
        elif user.updated_at and user.updated_at >= user.channel_updated_at:
            should_update = True

        # 3. Call Update Service if needed
        if should_update:
            try:
                update_service = UpdateChannelPostService(self.db)
                payload = UpdateChannelPostRequest(user_id=user_id)
                updated_user = await update_service.execute(payload)
                user = updated_user # Refresh user object
            except Exception as e:
                logger.error(f"Failed to update channel post for user {user_id}: {e}")
                raise ServiceError(
                    code="CHANNEL_SYNC_FAILED", 
                    message="Failed to synchronize user data with Telegram Channel", 
                    status_code=500
                )

        # 4. Fetch Formatter Components
        components = await self._fetch_formatter_components(user)
        if not isinstance(components, dict):
            components = {}

        # 5. Construct Final Flattened Data
        # We start with components, then overwrite/add the specific ID fields
        response_data = components.copy()
        
        response_data.update({
            "channel_message_id": user.telegram_message_id,
            "channel_id": getattr(settings, "MAIN_CHANNEL_ID", None),
            
            "group_message_id": user.group_message_id,
            "group_id": getattr(settings, "MAIN_GROUP_ID", None), # Assuming this exists in settings
            
            "public_group_message_id": user.public_group_message_id,
            "public_group_id": getattr(settings, "PUBLIC_GROUP_ID", None), # Assuming this exists in settings
            
            "public_message_id": user.public_message_id,
            "public_channel_id": getattr(settings, "PUBLIC_CHANNEL_ID", None)
        })

        return response_data

    async def _fetch_formatter_components(self, user: User) -> Dict[str, Any]:
        user_data = jsonable_encoder(user, exclude={"password", "token"})
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    settings.FORMATTER_WORKER_URL, 
                    json=user_data, 
                    timeout=90
                )
                if response.status_code != 200:
                    raise ServiceError(code="FORMATTER_ERROR", message="Formatter worker failed", status_code=502)
                
                try:
                    data = response.json()
                    return data.get("components", {})
                except ValueError:
                    raise ServiceError(code="FORMATTER_JSON_ERR", message="Invalid JSON from formatter", status_code=502)
            except httpx.RequestError:
                raise ServiceError(code="FORMATTER_CONN_ERR", message="Formatter unreachable", status_code=503)