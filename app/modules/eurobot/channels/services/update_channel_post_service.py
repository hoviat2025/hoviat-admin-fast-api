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

# Bot Instances
from app.shared.bot_instances import sender_bot, euro_bot, hilfen_bot

# Service Imports
from app.modules.eurobot.members.services.profile_service import save_user_profile_to_cloud
# Formatter Import
from app.modules.eurobot.channels.services.format_messages import create_telegram_message

logger = logging.getLogger(__name__)

class UpdateChannelPostService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = UserBaseRepository(db)

    async def execute(self, payload: UpdateChannelPostRequest | int, update_source: str = "eurobot") -> User:
        """
        Synchronises the user's channel posts with the database state.
        Accepts either an UpdateChannelPostRequest object or a raw integer user_id.

        Orchestration Flow:
        1. Stage 1 (Main Channel): Checks if main post exists. Edits caption if user 
           data changed since last update, or inserts a new main post if empty.
        2. Stage 2 (Sub-Channels): If a sub-channel (public or hilfen) is empty and
           the update_source matches, sends the corresponding message.
        3. Stage 3 (Confirmations): Polls database to verify webhook handshakes, 
           only waiting for the specific messages we actually dispatched.
        """
        if isinstance(payload, int):
            user_id = payload
        else:
            user_id = payload.user_id

        # 1. Fetch fresh, non-cached user record
        user = await self._get_user_or_404(user_id)

        # Execution flags to target confirmations on-demand
        sent_main = False
        sent_public = False
        sent_hilfen = False
        main_changed = False

        # ==========================================
        #   STAGE 1: Main Channel Message
        # ==========================================
        if user.telegram_message_id:
            main_msg_id = int(user.telegram_message_id)
            
            # Edit caption only if the user profile was modified after the last channel update
            if (
                user.updated_at is not None
                and user.channel_updated_at is not None
                and user.updated_at > user.channel_updated_at
            ):
                logger.info(f"User {user_id} main post exists but data is out of sync. Editing caption.")
                formatted_text = self._main_channel_formatter_local(user)
                await self._edit_caption_in_main_channel(main_msg_id, formatted_text)
                main_changed = True
        else:
            logger.info(f"User {user_id} main post is missing. Executing complete insert flow.")
            # Clear any stale sub-channel columns to ensure a fresh, consistent state
            await self._clear_sub_message_ids(user_id)

            # Retrieve profile photo using the correct bot instance matching the source
            picture_file, image_path, chat_not_found = await self._process_profile_image(user_id, update_source)

            # Persist and refresh the getChat result before formatting so the new
            # channel caption contains the value that was actually determined.
            await self._update_profile_fields(user_id, image_path, chat_not_found)
            await self.db.flush()
            user = await self._get_user_or_404(user_id)
            formatted_text = self._main_channel_formatter_local(user)

            # Post the main channel message
            main_msg_id = await self._send_photo_to_main_channel(
                formatted_text=formatted_text,
                picture_file=picture_file,
                user_id=user_id
            )
            sent_main = True
            main_changed = True
            
            # Commit profile properties before sending sub-channel replies.
            await self.db.commit()

        # ==========================================
        #   STAGE 2: Sub-Channel Messages (Independent Checks)
        # ==========================================
        # These are evaluated regardless of whether we ran an insert or update on the main channel.
        # Changed from if-elif to independent ifs to support updating both sub-channels
        # in a single pass when using 'both' update_source.
        if update_source in ["eurobot", "both"] and user.public_message_id is None:
            await self._send_user_post_in_public_channel(main_msg_id)
            sent_public = True
            logger.info(f"Public channel post sent for user {user_id}")
            
        if update_source in ["hilfenbot", "both"] and user.hilfen_message_id is None:
            await self._send_user_post_in_hilfen_channel(main_msg_id)
            sent_hilfen = True
            logger.info(f"Hilfen channel post sent for user {user_id}")

        # Sleep briefly to allow Telegram to process forwarding delays before polling begins
        if sent_main or sent_public or sent_hilfen:
            await asyncio.sleep(3)

        # ==========================================
        #   STAGE 3: Targeted Confirmations (Polling)
        # ==========================================
        if sent_main:
            user = await self._confirm_group_message(user_id)
            logger.info(f"DB Confirmed Main Message for {user_id}.")
            
        if sent_public:
            await self._confirm_public_group_post(user_id)
            logger.info(f"DB Confirmed Public Message for {user_id}.")
            
        if sent_hilfen:
            await self._confirm_hilfen_group_post(user_id)
            logger.info(f"DB Confirmed Hilfen Message for {user_id}.")

        # ==========================================
        #   STAGE 4: Finalize Timestamps
        # ==========================================
        if main_changed:
            current_time = datetime.now(timezone.utc)
            await self.repo.update(
                user_id=user_id,
                update_data={"channel_updated_at": current_time}
            )

        await self.db.commit()
        logger.info(f"Channel update completed successfully for {user_id}")
        
        # Return a completely fresh snapshot of the user record
        return await self.repo.get_fresh_by_id(user_id)

    # ==========================================
    #   HELPER FUNCTIONS
    # ==========================================

    async def _get_user_or_404(self, user_id: int) -> User:
        user = await self.repo.get_fresh_by_id(user_id)
        if not user:
            raise ServiceError(code="USER_NOT_FOUND", message=f"User {user_id} not found", status_code=404)
        return user

    async def _clear_sub_message_ids(self, user_id: int) -> None:
        """Wipes sub-channel IDs to ensure starting clean on a new main post."""
        await self.repo.update(
            user_id=user_id,
            update_data={
                "public_message_id": None,
                "public_group_message_id": None,
                "hilfen_message_id": None,
                "hilfen_group_message_id": None
            }
        )
        await self.db.flush()

    async def _process_profile_image(self, user_id: int, update_source: str) -> Tuple[str, Optional[str], bool]:
        """
        Retrieves user's profile picture using getChat.
        Always tries both bots (eurobot first, then hilfenbot) so users who
        only started one of the two bots still resolve their photo. A getChat
        failure on one bot is harmless - the chat simply is not visible to it.
        """
        chat_not_found = False
        picture_file = settings.DEFAULT_PROFILE_PICTURE
        image_path = None

        current_user = await self.repo.get_fresh_by_id(user_id)
        if current_user and current_user.profile_source == "user":
            if current_user.profile_path:
                media_base = settings.PROFILE_MEDIA_URL.rstrip("/")
                picture_file = (
                    f"{media_base}/{current_user.profile_path.lstrip('/')}"
                    if media_base
                    else settings.DEFAULT_PROFILE_PICTURE
                )
            # Do not call Telegram or create an orphaned bot image for a
            # profile picture explicitly controlled by the user.
            return picture_file, current_user.profile_path, current_user.chat_not_found

        chat_resp = None
        active_bot = euro_bot  # Default fallback bot

        # Try the primary bot first, then fall back to the other one. The
        # bot that succeeded is passed along so its own photo handle is used
        # for the cloud upload.
        chat_resp = await euro_bot.send_request("getChat", {"chat_id": str(user_id)})
        if chat_resp.success:
            active_bot = euro_bot
        else:
            logger.warning(
                f"getChat failed for {user_id} via euro_bot. Trying hilfen_bot fallback."
            )
            chat_resp = await hilfen_bot.send_request("getChat", {"chat_id": str(user_id)})
            if chat_resp.success:
                active_bot = hilfen_bot

        # Evaluate the final response
        if not chat_resp or not chat_resp.success:
            chat_not_found = True
            error_msg = chat_resp.error_message if chat_resp else "No response"
            logger.warning(f"getChat failed entirely for {user_id} via {update_source}: {error_msg}")
            return picture_file, image_path, chat_not_found

        photo_obj = chat_resp.data.get("result", {}).get("photo")
        if not photo_obj or not photo_obj.get("big_file_id"):
            return picture_file, image_path, chat_not_found

        # Pass the active bot instance that successfully completed the getChat request
        upload_result = await save_user_profile_to_cloud(user_id, bot=active_bot)

        if upload_result and isinstance(upload_result, dict):
             if upload_result.get("image_url") and upload_result.get("image_path"):
                 picture_file = upload_result["image_url"]
                 image_path = upload_result["image_path"]

        return picture_file, image_path, chat_not_found

    async def _update_profile_fields(self, user_id: int, image_path: Optional[str], chat_not_found: bool) -> None:
        current_user = await self.repo.get_fresh_by_id(user_id)
        update_data = {"chat_not_found": chat_not_found}

        # A user-uploaded image is authoritative. Telegram sync must not
        # overwrite or clear it during a later channel update.
        if not current_user or current_user.profile_source != "user":
            update_data["profile_path"] = image_path
            update_data["profile_source"] = "telegram" if image_path else None

        await self.repo.update(
            user_id=user_id,
            update_data=update_data
        )

    def _main_channel_formatter_local(self, user: User) -> str:
        try:
            user_data = jsonable_encoder(user, exclude={"password", "token"})
            result = create_telegram_message(user_data)
            return result.get("text")
        except Exception as e:
            logger.error(f"Local formatter failed for user {user.user_id}: {e}")
            raise ServiceError(
                code="FORMATTER_ERROR", 
                message="Local message formatting failed", 
                status_code=500
            )

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
        
        try:
            message_id = result.data["result"]["message_id"]
            return message_id
        except (KeyError, TypeError) as e:
            logger.error(f"Failed to extract message_id from API response for user {user_id}: {e}")
            raise ServiceError(code="TELEGRAM_API_ERROR", message="Failed to parse message ID", status_code=502)

    async def _send_user_post_in_public_channel(self, telegram_message_id: int) -> bool:
        payload = {
            "chat_id": settings.PUBLIC_CHANNEL_ID,
            "text": "❗️مشتری جدید\nستاره ها : « ⭐️⭐️⭐️⭐️⭐️ »\nتعداد کنسلی ❌❌❌❌❌",
            "reply_parameters": {
                "message_id": telegram_message_id,
                "chat_id": settings.MAIN_CHANNEL_ID
            }
        }
        result = await sender_bot.send_request("sendMessage", payload)
        if not result.success:
            logger.error(f"Telegram Public Send Failed: {result.error_message}")
            raise Exception(f"Failed to send public post: {result.error_message}")
        return True

    async def _send_user_post_in_hilfen_channel(self, telegram_message_id: int) -> bool:
        payload = {
            "chat_id": settings.HILFEN_CHANNEL_ID,
            "text": "❗️مشتری جدید\nستاره ها : « ⭐️⭐️⭐️⭐️⭐️ »\nتعداد کنسلی ❌❌❌❌❌",
            "reply_parameters": {
                "message_id": telegram_message_id,
                "chat_id": settings.MAIN_CHANNEL_ID
            }
        }
        result = await sender_bot.send_request("sendMessage", payload)
        if not result.success:
            logger.error(f"Telegram Hilfen Send Failed: {result.error_message}")
            raise Exception(f"Failed to send Hilfen post: {result.error_message}")
        return True

    # ==========================================
    #   CONFIRMATION POLLING HELPERS
    # ==========================================

    async def _confirm_group_message(self, user_id: int) -> User:
        return await self._confirm_field(user_id, "group_message_id", "Main")

    async def _confirm_public_group_post(self, user_id: int) -> User:
        return await self._confirm_field(user_id, "public_group_message_id", "Public")

    async def _confirm_hilfen_group_post(self, user_id: int) -> User:
        return await self._confirm_field(user_id, "hilfen_group_message_id", "Hilfen")

    async def _confirm_field(self, user_id: int, field_name: str, label: str) -> User:
        """
        Polling harness. Commits inside the loop to refresh the transaction read-snapshot, 
        and uses get_fresh_by_id to avoid SQLAlchemy identity map cache.
        """
        start_time = datetime.now()
        timeout_seconds = 45
        
        while (datetime.now() - start_time).total_seconds() < timeout_seconds:
            await self.db.commit()
            
            user = await self.repo.get_fresh_by_id(user_id)
            if user:
                val = getattr(user, field_name, None)
                if val is not None:
                    logger.info(f"{label} group message confirmed for {user_id}: {val}")
                    return user
            
            await asyncio.sleep(5)
            
        logger.error(f"Timeout waiting for {label} {field_name} for user {user_id}")
        raise ServiceError(
            code="CONFIRM_TIMEOUT", 
            message=f"Timed out waiting for {label} Group Message ID confirmation", 
            status_code=500
        )

    # ==========================================
    #   DATABASE UPDATE HELPERS
    # ==========================================

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
