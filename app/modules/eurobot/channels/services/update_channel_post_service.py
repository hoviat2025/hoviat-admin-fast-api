import logging
import asyncio
from datetime import datetime, timezone
from typing import Tuple, Optional

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
# Formatter Import
from app.modules.eurobot.channels.services.format_messages import create_telegram_message

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
       
        # Generate formatted text locally
        formatted_text = self._main_channel_formatter_local(user)

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

        # 2. Formatter (Local)
        formatted_text = self._main_channel_formatter_local(user)

        try:
            # --- STEP A: Send Main Channel Message ---
            # We get the ID immediately to use in the next step
            main_msg_id = await self._send_photo_to_main_channel(
                formatted_text=formatted_text,
                picture_file=picture_file,
                user_id=user_id
            )
            # FIXED: Replaced print() with logger.info()
            logger.info(f"Main channel photo sent for {user_id}. API returned ID: {main_msg_id}")
            await asyncio.sleep(15)

            # --- STEP B: Send Public Channel Message ---
            await self._send_user_post_in_public_channel(main_msg_id)
            logger.info(f"Public channel post sent for {user_id} referencing ID {main_msg_id}")
            await asyncio.sleep(15)

            # --- STEP B2: Send Hilfen Channel Message ---
            # Mirrors the public channel logic; uses a dedicated text helper for easy customisation.
            await self._send_user_post_in_hilfen_channel(main_msg_id)
            logger.info(f"Hilfen channel post sent for {user_id} referencing ID {main_msg_id}")
             
            await asyncio.sleep(3)

            # --- STEP C: Confirm Main Channel Webhook ---
            # Now we wait for the webhook to update the DB for the first message
            user = await self._confirm_group_message(user_id)
            logger.info(f"DB Confirmed Main Message. TG_MSG_ID: {user.telegram_message_id}, GRP_MSG_ID: {user.group_message_id}")

            # --- STEP D: Confirm Public Channel Webhook ---
            await self._confirm_public_group_post(user_id)
            logger.info(f"DB Confirmed Public Message.")

            # --- STEP E: Confirm Hilfen Channel Webhook ---
            await self._confirm_hilfen_group_post(user_id)
            logger.info(f"DB Confirmed Hilfen Message.")

        except Exception as e:
            # Strategic Error Logging & Rollback
            logger.error(f"CRITICAL: Insert Flow Failed for {user_id}. Error: {str(e)}", exc_info=True)
            logger.info(f"Initiating Rollback (NULL updates) for {user_id}")
           
            try:
                await self._update_channel_posts_to_null(user_id, chat_not_found)
                await self.db.commit()
                logger.info(f"Rollback committed successfully for {user_id}")
            except Exception as rollback_error:
                logger.critical(f"FATAL: Rollback failed for {user_id}: {rollback_error}")
           
            # Re-raise to 500
            raise ServiceError(code="INSERT_FLOW_FAILED", message="Failed to set posts", status_code=500)

        # 3. Final DB Update (Success)
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

    def _main_channel_formatter_local(self, user: User) -> str:
        """
        Replaces external API call with local function execution.
        """
        try:
            # Prepare data
            user_data = jsonable_encoder(user, exclude={"password", "token"})
           
            # Execute logic
            result = create_telegram_message(user_data)
           
            # Extract text
            return result.get("text")
       
        except Exception as e:
            logger.error(f"Local formatter failed for user {user.user_id}: {e}")
            raise ServiceError(
                code="FORMATTER_ERROR",
                message="Local message formatting failed",
                status_code=500
            )

    # ------------------------------------------------------------------
    #  Text builders for the secondary channel posts
    # ------------------------------------------------------------------

    def _build_public_post_text(self) -> str:
        """Returns the caption / text sent to the public channel.
        Kept as a separate method so it can be modified independently later.
        """
        return "❗️مشتری جدید\nستاره ها : « ⭐️⭐️⭐️⭐️⭐️ »\nتعداد کنسلی ❌❌❌❌❌"

    def _build_hilfen_post_text(self) -> str:
        """Returns the caption / text sent to the hilfen channel.
        Currently identical to the public post; change this method when differentiation is needed.
        """
        return "❗️مشتری جدید\nستاره ها : « ⭐️⭐️⭐️⭐️⭐️ »\nتعداد کنسلی ❌❌❌❌❌"

    # ------------------------------------------------------------------
    #  Telegram API helpers
    # ------------------------------------------------------------------

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

    async def _send_photo_to_main_channel(self, formatted_text: str, picture_file: str, user_id: int) -> int:
        """
        Sends the photo and returns the Message ID immediately.
        """
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
       
        # Extract Message ID directly from the API response
        try:
            message_id = result.data["result"]["message_id"]
            return message_id
        except (KeyError, TypeError) as e:
            logger.error(f"Failed to extract message_id from API response for user {user_id}: {e}")
            raise ServiceError(code="TELEGRAM_API_ERROR", message="Failed to parse message ID", status_code=502)

    # --- Public channel helpers ---

    async def _send_user_post_in_public_channel(self, telegram_message_id: int) -> bool:
        """
        Sends the public post referencing the main channel ID immediately.
        """
        payload = {
           "chat_id": settings.PUBLIC_CHANNEL_ID,
           "text": self._build_public_post_text(),
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
       
        return True

    # FIXED: Added the previously missing _confirm_group_message polling function. 
    # Calling this was raising an AttributeError and breaking the flow.
    async def _confirm_group_message(self, user_id: int) -> User:
        """Polls the database until the group_message_id is populated by the webhook for the main channel."""
        start_time = datetime.now()
        timeout = 45
        while (datetime.now() - start_time).total_seconds() < timeout:
            await self.db.commit()
            user = await self.repo.get_fresh_by_id(user_id)
            if user and user.group_message_id is not None:
                logger.info(f"Main Group Message Confirmed: {user.group_message_id}")
                return user
            await asyncio.sleep(5)
           
        logger.error(f"Timeout waiting for MAIN group_message_id for user {user_id}")
        raise Exception("Timed out waiting for Main Group Message ID")

    async def _confirm_public_group_post(self, user_id: int) -> User:
        start_time = datetime.now()
        timeout = 45
        while (datetime.now() - start_time).total_seconds() < timeout:
            # Commit to see parallel updates.
            await self.db.commit()
           
            # USE NEW REPO METHOD: get_fresh_by_id
            user = await self.repo.get_fresh_by_id(user_id)
           
            if user:
                if user.public_group_message_id is not None:
                    logger.info(f"Public Group Message Confirmed: {user.public_group_message_id}")
                    return user
            await asyncio.sleep(5)
           
        logger.error(f"Timeout waiting for PUBLIC group_message_id for user {user_id}")
        raise Exception("Timed out waiting for Public Group Message ID")

    # --- Hilfen channel helpers ---
    # These methods mirror the public channel helpers exactly.

    async def _send_user_post_in_hilfen_channel(self, telegram_message_id: int) -> bool:
        """Sends the hilfen post referencing the main channel message."""
        payload = {
            "chat_id": settings.HILFEN_CHANNEL_ID,
            "text": self._build_hilfen_post_text(),
            "reply_parameters": {
                "message_id": telegram_message_id,
                "chat_id": settings.MAIN_CHANNEL_ID
            }
        }
        logger.info(f"Sending hilfen msg payload: {payload}")

        result = await sender_bot.send_request("sendMessage", payload)
        if not result.success:
            logger.error(f"Telegram Hilfen Send Failed: {result.error_message}")
            raise Exception(f"Failed to send hilfen post: {result.error_message}")

        return True

    async def _confirm_hilfen_group_post(self, user_id: int) -> User:
        """Polls the database until the hilfen_group_message_id is populated by the webhook."""
        start_time = datetime.now()
        timeout = 45
        while (datetime.now() - start_time).total_seconds() < timeout:
            await self.db.commit()
            user = await self.repo.get_fresh_by_id(user_id)
            if user and user.hilfen_group_message_id is not None:
                logger.info(f"Hilfen Group Message Confirmed: {user.hilfen_group_message_id}")
                return user
            await asyncio.sleep(5)

        logger.error(f"Timeout waiting for HILFEN group_message_id for user {user_id}")
        raise Exception("Timed out waiting for Hilfen Group Message ID")

    # --- Rollback & finalisation ---

    async def _update_channel_posts_to_null(self, user_id: int, chat_not_found: bool) -> bool:
        """Rollback that clears all channel message IDs (including hilfen)."""
        logger.warning(f"Executing NULL Rollback for User {user_id}")
        update_data = {
            "telegram_message_id": None,
            "group_message_id": None,
            "public_message_id": None,
            "public_group_message_id": None,
            "hilfen_message_id": None,
            "hilfen_group_message_id": None,
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


