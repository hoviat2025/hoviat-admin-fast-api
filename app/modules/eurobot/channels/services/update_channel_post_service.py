import httpx
import logging
import asyncio
from datetime import datetime, timezone
from typing import Tuple, Optional, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.encoders import jsonable_encoder

# Architecture Imports
from app.core.config import settings
from app.models.user import User
from app.shared.repositories.user_base import UserBaseRepository
from app.core.exceptions import ServiceError
from app.modules.eurobot.channels.schemas.update_post_request import UpdateChannelPostRequest

# Bot Imports
from app.shared.bot_instances import sender_bot, euro_bot

# Service Imports
from app.modules.eurobot.members.services.profile_service import save_user_profile_to_cloud

# Correct Logger Initialization
logger = logging.getLogger(__name__)

class UpdateChannelPostService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = UserBaseRepository(db)

    async def execute(self, payload: UpdateChannelPostRequest) -> User:
        """
        Orchestrator function.
        Decides between UPDATE or INSERT flow based on telegram_message_id.
        """
        user_id = payload.user_id
        
        # 1. Get User Info
        user = await self._get_user_or_404(user_id)

        # 2. Decision Tree
        if user.telegram_message_id:
            logger.info(f"User {user_id} exists in channel. Starting UPDATE flow.")
            return await self._handle_update_flow(user)
        else:
            logger.info(f"User {user_id} not in channel. Starting INSERT flow.")
            return await self._handle_insert_flow(user)

    # ==========================================
    #   FLOW HANDLERS
    # ==========================================

    async def _handle_update_flow(self, user: User) -> User:
        logger.info(f"Starting Update Flow for {user.user_id}")
        formatted_text = await self._main_channel_formatter(user)

        await self._edit_caption_in_main_channel(
            message_id=user.telegram_message_id, 
            formatted_text=formatted_text
        )

        updated_user = await self._update_channel_updated_at(user.user_id)
        await self.db.commit()
        logger.info(f"Update Flow Successful for {user.user_id}")
        return updated_user

    async def _handle_insert_flow(self, user: User) -> User:
        user_id = user.user_id
        logger.info(f"Starting Insert Flow for {user_id}")

        # 1. Process Profile Image
        picture_file, image_path, chat_not_found = await self._process_profile_image(user_id)
        logger.info(f"Profile processed: ImagePath={image_path}, ChatNotFound={chat_not_found}")

        # 2. Formatter
        formatted_text = await self._main_channel_formatter(user)

        # 3. Send Photo to Main Channel
        await self._send_photo_to_main_channel(
            formatted_text=formatted_text,
            picture_file=picture_file,
            user_id=user_id
        )
        logger.info(f"Main channel photo sent for {user_id}. Waiting for DB Webhook confirmation...")
        
        # 4. Confirm Group Message (Polling DB)
        # This refreshes the user object with the new IDs
        user = await self._confirm_group_message(user_id)
        logger.info(f"Group Message Confirmed. TG_MSG_ID: {user.telegram_message_id}, GRP_MSG_ID: {user.group_message_id}")

        # 5. Set Public Channel Posts
        try:
            await self._set_public_channel_posts(user)
            logger.info(f"Public channel flow finished for {user_id}")
        except Exception as e:
            # Strategic Error Logging
            logger.error(f"CRITICAL: Public Post Flow Failed for {user_id}. Error: {str(e)}")
            logger.info(f"Initiating Rollback (NULL updates) for {user_id}")
            
            try:
                await self._update_channel_posts_to_null(user_id, chat_not_found)
                await self.db.commit()
                logger.info(f"Rollback committed successfully for {user_id}")
            except Exception as rollback_error:
                logger.critical(f"FATAL: Rollback failed for {user_id}: {rollback_error}")
            
            # Re-raise to 500 as per pseudo-code
            raise ServiceError(code="PUBLIC_POST_FAILED", message="Failed to set public posts", status_code=500)

        # 6. Final DB Update (Success)
        final_user = await self._update_profile_and_success_fields(
            user_id=user_id,
            image_path=image_path,
            chat_not_found=chat_not_found
        )

        await self.db.commit()
        logger.info(f"Insert Flow Complete & Committed for {user_id}")
        return final_user

    # ==========================================
    #   HELPER FUNCTIONS
    # ==========================================

    async def _get_user_or_404(self, user_id: int) -> User:
        user = await self.repo.get_by_id(user_id)
        if not user:
            raise ServiceError(code="USER_NOT_FOUND", message=f"User {user_id} not found", status_code=404)
        return user

    async def _process_profile_image(self, user_id: int) -> Tuple[str, Optional[str], bool]:
        chat_not_found = False
        picture_file = settings.DEFAULT_PROFILE_PICTURE
        image_path = None

        chat_resp = await euro_bot.send_request("getChat", {"chat_id": str(user_id)})

        if not chat_resp.success:
            chat_not_found = True
            logger.warning(f"getChat failed for {user_id}: {chat_resp.error_message}")
            return picture_file, image_path, chat_not_found

        photo_obj = chat_resp.data.get("result", {}).get("photo")
        if not photo_obj or not photo_obj.get("big_file_id"):
            return picture_file, image_path, chat_not_found

        upload_result = await save_user_profile_to_cloud(user_id)

        if upload_result and isinstance(upload_result, dict):
             if upload_result.get("image_url") and upload_result.get("image_path"):
                 picture_file = upload_result["image_url"]
                 image_path = upload_result["image_path"]

        return picture_file, image_path, chat_not_found

    async def _main_channel_formatter(self, user: User) -> str:
        user_data = jsonable_encoder(user, exclude={"password", "token"})
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(settings.FORMATTER_WORKER_URL, json=user_data, timeout=10.0)
                if response.status_code != 200:
                    raise ServiceError(code="FORMATTER_ERROR", message=f"Worker returned {response.status_code}", status_code=502)
                
                try:
                    data = response.json()
                    return data.get("text")
                except:
                     raise ServiceError(code="FORMATTER_JSON_ERR", message="Invalid JSON", status_code=502)
            except httpx.RequestError:
                raise ServiceError(code="FORMATTER_CONN_ERR", message="Unreachable", status_code=503)

    async def _edit_caption_in_main_channel(self, message_id: int, formatted_text: str) -> bool:
        payload = {
            "chat_id": settings.MAIN_CHANNEL_ID,
            "message_id": message_id,
            "caption": formatted_text,
            "parse_mode": "HTML"
        }
        result = await sender_bot.send_request("editMessageCaption", payload)
        if not result.success:
            logger.error(f"Telegram Edit Failed: {result.error_message}")
            raise ServiceError(code="TELEGRAM_EDIT_FAILED", message="Edit caption failed", status_code=502)
        return True

    async def _send_photo_to_main_channel(self, formatted_text: str, picture_file: str, user_id: int) -> bool:
        payload = {
            "chat_id": settings.MAIN_CHANNEL_ID,
            "photo": picture_file,
            "caption": formatted_text,
            "parse_mode": "HTML"
        }
        result = await sender_bot.send_request("sendPhoto", payload)
        
        if not result.success:
             logger.error(f"Send Photo Failed: {result.error_message}")
             raise ServiceError(code="TELEGRAM_SEND_FAILED", message="Send photo failed", status_code=502)
        return True

    async def _confirm_group_message(self, user_id: int) -> User:
        """
        Polls DB until group_message_id appears.
        Includes Session Expiration to ensure we see Webhook updates.
        """
        start_time = datetime.now()
        timeout_seconds = 20
        
        while (datetime.now() - start_time).total_seconds() < timeout_seconds:
            # FIX 1: expire_all is SYNCHRONOUS. Do not await it.
            # This invalidates the cache so the next 'get_by_id' fetches fresh data from DB.
            self.db.expire_all()
            
            user = await self.repo.get_by_id(user_id)
            
            if user:
                if user.group_message_id is not None:
                    # Also ensure telegram_message_id is visible, as we need it next
                    if user.telegram_message_id is not None:
                        return user
            
            await asyncio.sleep(0.5)
            
        logger.error(f"Timeout waiting for group_message_id for user {user_id}")
        raise ServiceError(
            code="CONFIRM_TIMEOUT", 
            message="Timed out waiting for Group Message ID confirmation", 
            status_code=500
        )

    async def _set_public_channel_posts(self, user: User) -> bool:
        if not user.telegram_message_id:
             logger.error(f"Cannot set public post: telegram_message_id is None for user {user.user_id}")
             raise Exception("telegram_message_id missing during public post set")

        logger.info(f"Sending Public Post for User {user.user_id} referencing Msg {user.telegram_message_id}")
        
        # 1. Send Post
        await self._send_user_post_in_public_channel(user.telegram_message_id)

        # 2. Confirm Post
        await self._confirm_public_group_post(user.user_id)
        
        return True

    async def _send_user_post_in_public_channel(self, telegram_message_id: int) -> bool:
        payload = {
           "chat_id": settings.PUBLIC_CHANNEL_ID,
           "text": "❗️مشتری جدید\nستاره ها : « ⭐️⭐️⭐️⭐️⭐️ »\nتعداد کنسلی ❌❌❌❌❌",
           "reply_parameters": {
               "message_id": telegram_message_id,
               "chat_id": settings.MAIN_CHANNEL_ID
           }
        }
        logger.info(f"Sending public msg payload: {payload}")
        
        result = await sender_bot.send_request("sendMessage", payload)
        if not result.success:
            logger.error(f"Telegram Public Send Failed: {result.error_message}")
            raise Exception(f"Failed to send public post: {result.error_message}")
        
        logger.info("Public post sent successfully (according to Bot API).")
        return True

    async def _confirm_public_group_post(self, user_id: int) -> User:
        start_time = datetime.now()
        timeout = 20
        while (datetime.now() - start_time).total_seconds() < timeout:
            # FIX 2: expire_all is SYNCHRONOUS. Do not await it.
            self.db.expire_all()
            
            user = await self.repo.get_by_id(user_id)
            if user and user.public_group_message_id is not None:
                logger.info(f"Public Group Message Confirmed: {user.public_group_message_id}")
                return user
            await asyncio.sleep(0.5)
            
        logger.error(f"Timeout waiting for PUBLIC group_message_id for user {user_id}")
        raise Exception("Timed out waiting for Public Group Message ID")

    async def _update_channel_posts_to_null(self, user_id: int, chat_not_found: bool) -> bool:
        """
        Rollback function on failure.
        """
        logger.warning(f"Executing NULL Rollback for User {user_id}")
        update_data = {
            "telegram_message_id": None,
            "group_message_id": None,
            "public_message_id": None,
            "public_group_message_id": None,
            "chat_not_found": chat_not_found
        }
        await self.repo.update(user_id=user_id, update_data=update_data)
        return True

    async def _update_profile_and_success_fields(self, user_id: int, image_path: Optional[str], chat_not_found: bool) -> User:
        current_time = datetime.now(timezone.utc)
        update_data = {
            "channel_updated_at": current_time,
            "chat_not_found": chat_not_found,
            "profile_path": image_path 
        }
        updated_user = await self.repo.update(user_id=user_id, update_data=update_data)
        if not updated_user:
            raise ServiceError(code="DB_UPDATE_FAILED", message="Final DB update failed", status_code=500)
        return updated_user
        
    async def _update_channel_updated_at(self, user_id: int) -> User:
        current_time = datetime.now(timezone.utc) 
        updated_user = await self.repo.update(
            user_id=user_id,
            update_data={"channel_updated_at": current_time}
        )
        if not updated_user:
            raise ServiceError(code="DB_UPDATE_FAILED", message="DB update failed", status_code=500)
        return updated_user