import httpx
import logging
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.encoders import jsonable_encoder

# Architecture Imports
from app.core.config import settings
from app.models.user import User
from app.shared.repositories.user_base import UserBaseRepository
from app.core.exceptions import ServiceError
from app.modules.eurobot.channels.schemas.update_post_request import UpdateChannelPostRequest

# Bot Imports
from app.shared.bot_instances import sender_bot

logger = logging.getLogger(__name__)

class UpdateChannelPostService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = UserBaseRepository(db)

    async def execute(self, payload: UpdateChannelPostRequest) -> User:
        """
        Orchestrator function.
        Returns a success message or raises ServiceError.
        """
        user_id = payload.user_id
        
        # 1. Get User Info
        user = await self._get_user_or_404(user_id)

        # 2. Skip if not in channel
        if not user.telegram_message_id:
            logger.info(f"User {user_id} has no telegram_message_id. Skipping update.")
            # Return the original user object since we didn't update anything
            return user

        # 3. Formatter (External Worker)
        formatted_text = await self._main_channel_formatter(user)

        # 4. Telegram Edit (External API)
        await self._edit_caption_in_main_channel(
            message_id=user.telegram_message_id, 
            formatted_text=formatted_text
        )

        # 5. Update DB Timestamp
        # This returns the UPDATED row
        updated_user = await self._update_channel_updated_at(user_id)

        # 6. Commit (Atomic Transaction)
        # We only commit if all previous steps succeeded
        await self.db.commit()

        logger.info(f"Successfully updated channel post for User {user_id}")
        # CHANGED: Return the user object
        return updated_user

    # ==========================================
    #   HELPER FUNCTIONS (The "Black Boxes")
    # ==========================================

    async def _get_user_or_404(self, user_id: int) -> User:
        # FIXED: Changed .get() to .get_by_id()
        user = await self.repo.get_by_id(user_id)
        
        if not user:
            raise ServiceError(
                code="USER_NOT_FOUND",
                message=f"User {user_id} not found",
                status_code=404
            )
        return user

    async def _main_channel_formatter(self, user: User) -> str:
        """
        Sends user data to Cloudflare Worker to get HTML text.
        Expects worker response: {"text": "<b>Formatted HTML</b>"}
        """
        # SAFE SERIALIZATION
        user_data = jsonable_encoder(user, exclude={"password", "token"})

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    settings.FORMATTER_WORKER_URL, 
                    json=user_data, 
                    timeout=10.0
                )
                
                if response.status_code != 200:
                    logger.error(f"Formatter Worker failed: {response.text}")
                    raise ServiceError(
                        code="FORMATTER_ERROR",
                        message=f"Formatter worker returned {response.status_code}",
                        status_code=502
                    )
                
                # --- FIX IS HERE ---
                try:
                    data = response.json() # Parse JSON
                except Exception:
                    raise ServiceError(
                        code="FORMATTER_INVALID_JSON",
                        message="Formatter did not return valid JSON",
                        status_code=502
                    )

                # Get the specific 'text' field
                formatted_text = data.get("text")
                
                if not formatted_text:
                    logger.error(f"Formatter response missing 'text' field. Response: {data}")
                    raise ServiceError(
                        code="FORMATTER_MISSING_FIELD",
                        message="Formatter response missing 'text' field",
                        status_code=502
                    )

                return formatted_text
                
            except httpx.RequestError as e:
                logger.error(f"Formatter Connection Error: {e}")
                raise ServiceError(
                    code="FORMATTER_CONN_ERR", 
                    message="Could not reach formatting service", 
                    status_code=503
                )

    async def _edit_caption_in_main_channel(self, message_id: int, formatted_text: str) -> bool:
        """
        Uses the shared sender_bot to edit the message.
        """
        print(formatted_text)
        payload = {
            "chat_id": settings.MAIN_CHANNEL_ID,
            "message_id": message_id,
            "caption": formatted_text
        }

        # Multi-Tenant Bot Usage
        result = await sender_bot.send_request("editMessageCaption", payload)

        if not result.success:
            # LOG the specific error from Telegram for debugging
            logger.error(f"Telegram Edit Failed for Msg {message_id}: {result.error_message}")
            
            # Raise generic error to client
            raise ServiceError(
                code="TELEGRAM_EDIT_FAILED",
                message="Failed to update Telegram Channel",
                status_code=502
            )
        
        return True

    async def _update_channel_updated_at(self, user_id: int) -> User:
        """
        Updates the channel_updated_at field in DB.
        """
        # FIX: The Database expects a Python datetime object, NOT an integer timestamp.
        current_time = datetime.now(timezone.utc) 

        updated_user = await self.repo.update(
            user_id=user_id,
            update_data={"channel_updated_at": current_time}
        )
        
        if not updated_user:
            raise ServiceError(code="DB_UPDATE_FAILED", message="Database update failed", status_code=500)
            
        return updated_user