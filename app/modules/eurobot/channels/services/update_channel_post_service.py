import logging
import asyncio
from datetime import datetime, timezone
from typing import Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.encoders import jsonable_encoder

from app.core.config import settings
from app.models.user import User
from app.shared.repositories.user_base import UserBaseRepository
from app.core.exceptions import ServiceError
from app.shared.bot_instances import sender_bot, euro_bot, hilfen_bot
from app.modules.eurobot.members.services.profile_service import save_user_profile_to_cloud
from app.modules.eurobot.channels.services.format_messages import create_telegram_message
from app.modules.hilfen.services.admin_message import build_admin_post_text

logger = logging.getLogger(__name__)

class UpdateChannelPostService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = UserBaseRepository(db)

    async def execute(self, user_id: int, update_source: str = "eurobot") -> User:
        """
        Synchronises the user's channel posts with the database state.

        Decision tree:
        - If main post exists and user data changed since last channel update → edit caption.
        - If main post does NOT exist → clear sub‑message IDs, send new main post.
        - Then, for each sub‑channel (public / hilfen / admin), if its ID is NULL and
          the update_source matches, send the corresponding message.
        - Every sent message is confirmed via polling.

        The ``update_source`` switches which sub‑channels are created:
            - ``"eurobot"`` → public channel
            - ``"hilfenbot"`` → hilfen + admin channels
        """
        user = await self._get_user_or_404(user_id)

        # ---- Stage 1: Main Channel Message ---------------------------------
        main_msg_id: Optional[int] = None
        sent_main = False
        main_changed = False    # will be True only if main post was created or edited

        if user.telegram_message_id is not None:
            # Existing main post
            main_msg_id = int(user.telegram_message_id)
            if (
                user.updated_at is not None
                and user.channel_updated_at is not None
                and user.updated_at > user.channel_updated_at
            ):
                # User data changed after the last channel update → edit caption
                formatted_text = self._main_channel_formatter_local(user)
                await self._edit_caption_in_main_channel(main_msg_id, formatted_text)

                main_changed = True
        else:
            # No main post – start from scratch
            await self._clear_sub_message_ids(user_id)

            picture_file, image_path, chat_not_found = await self._process_profile_image(
                user_id, update_source=update_source
            )
            formatted_text = self._main_channel_formatter_local(user)

            main_msg_id = await self._send_photo_to_main_channel(
                formatted_text=formatted_text,
                picture_file=picture_file,
                user_id=user_id,
            )
            sent_main = True
            main_changed = True
            logger.info(f"Main channel photo sent for {user_id}. ID: {main_msg_id}")

            await self._update_profile_fields(user_id, image_path, chat_not_found)

        # ---- Stage 2: Sub‑Channel Messages (only when NULL and source matches) ----
        sent_public = False
        sent_hilfen = False
        sent_admin = False

        if (
            update_source == "eurobot"
            and user.public_message_id is None
        ):
            await self._send_user_post_in_public_channel(main_msg_id)
            sent_public = True
            logger.info(f"Public channel post sent for {user_id}")

        if (
            update_source == "hilfenbot"
            and user.hilfen_message_id is None
        ):
            await self._send_user_post_in_hilfen_channel(main_msg_id)
            sent_hilfen = True
            logger.info(f"Hilfen channel post sent for {user_id}")

        if (
            update_source == "hilfenbot"
            and user.admin_message_id is None
        ):
            await self._send_user_post_in_admin_channel(main_msg_id)
            sent_admin = True
            logger.info(f"Admin channel post sent for {user_id}")

        # ---- Stage 3: Confirmations (only for messages we actually sent) ----
        if sent_main:
            await self._confirm_group_message(user_id)
        if sent_public:
            await self._confirm_public_group_post(user_id)
        if sent_hilfen:
            await self._confirm_hilfen_group_post(user_id)
        if sent_admin:
            await self._confirm_admin_group_post(user_id)

        # ---- Finalise: update channel_updated_at only when the main post changed ----
        if main_changed:
            current_time = datetime.now(timezone.utc)
            await self.repo.update(
                user_id=user_id,
                update_data={"channel_updated_at": current_time},
            )

        await self.db.commit()
        logger.info(f"Channel update completed for {user_id}")
        # Return a fresh copy of the user for the caller
        return await self.repo.get_fresh_by_id(user_id)

    # ------------------------------------------------------------------
    #   Helpers
    # ------------------------------------------------------------------

    async def _get_user_or_404(self, user_id: int) -> User:
        user = await self.repo.get_fresh_by_id(user_id)
        if not user:
            raise ServiceError(
                code="USER_NOT_FOUND",
                message=f"User {user_id} not found",
                status_code=404,
            )
        return user

    async def _clear_sub_message_ids(self, user_id: int) -> None:
        await self.repo.update(
            user_id=user_id,
            update_data={
                "public_message_id": None,
                "public_group_message_id": None,
                "hilfen_message_id": None,
                "hilfen_group_message_id": None,
                "admin_message_id": None,
                "admin_group_message_id": None,
            },
        )
        await self.db.flush()

    async def _process_profile_image(
        self, user_id: int, update_source: str = "eurobot"
    ) -> Tuple[str, Optional[str], bool]:
        """
        Fetch the user's profile photo using the bot instance that matches
        ``update_source``. Falls back to the default picture on any failure.
        """
        chat_not_found = False
        picture_file = settings.DEFAULT_PROFILE_PICTURE
        image_path = None

        # Choose the correct bot instance based on the update source
        if update_source == "hilfenbot":
            bot = hilfen_bot
        else:
            bot = euro_bot

        chat_resp = await bot.send_request("getChat", {"chat_id": str(user_id)})
        if not chat_resp.success:
            chat_not_found = True
            logger.warning(f"getChat failed for {user_id} (source={update_source}): {chat_resp.error_message}")
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

    async def _update_profile_fields(self, user_id: int, image_path: Optional[str], chat_not_found: bool) -> None:
        await self.repo.update(
            user_id=user_id,
            update_data={
                "profile_path": image_path,
                "chat_not_found": chat_not_found,
            },
        )

    def _main_channel_formatter_local(self, user: User) -> str:
        try:
            user_data = jsonable_encoder(user, exclude={"password", "token"})
            result = create_telegram_message(user_data)
            return result.get("text")
        except Exception as e:
            logger.error(f"Local formatter failed for {user.user_id}: {e}")
            raise ServiceError(
                code="FORMATTER_ERROR",
                message="Local message formatting failed",
                status_code=500,
            )

    def _build_public_post_text(self) -> str:
        return "❗️مشتری جدید\nستاره ها : « ⭐️⭐️⭐️⭐️⭐️ »\nتعداد کنسلی ❌❌❌❌❌"

    def _build_hilfen_post_text(self) -> str:
        return "❗️مشتری جدید\nستاره ها : « ⭐️⭐️⭐️⭐️⭐️ »\nتعداد کنسلی ❌❌❌❌❌"

    def _build_admin_post_text(self) -> str:
        return build_admin_post_text()

    # --- Telegram API helpers ---

    async def _edit_caption_in_main_channel(self, message_id: int, formatted_text: str) -> None:
        payload = {
            "chat_id": settings.MAIN_CHANNEL_ID,
            "message_id": message_id,
            "caption": formatted_text,
            "parse_mode": "HTML",
        }
        result = await sender_bot.send_request("editMessageCaption", payload)
        if not result.success:
            logger.error(f"Telegram Edit Failed: {result.error_message}")
            raise ServiceError(
                code="TELEGRAM_EDIT_FAILED",
                message="Edit caption failed",
                status_code=502,
            )

    async def _send_photo_to_main_channel(self, formatted_text: str, picture_file: str, user_id: int) -> int:
        payload = {
            "chat_id": settings.MAIN_CHANNEL_ID,
            "photo": picture_file,
            "caption": formatted_text,
            "parse_mode": "HTML",
        }
        result = await sender_bot.send_request("sendPhoto", payload)
        if not result.success:
            logger.error(f"Send Photo Failed: {result.error_message}")
            raise ServiceError(
                code="TELEGRAM_SEND_FAILED",
                message="Send photo failed",
                status_code=502,
            )
        try:
            return result.data["result"]["message_id"]
        except (KeyError, TypeError) as e:
            logger.error(f"Failed to extract message_id for {user_id}: {e}")
            raise ServiceError(
                code="TELEGRAM_API_ERROR",
                message="Failed to parse message ID",
                status_code=502,
            )

    async def _send_user_post_in_public_channel(self, telegram_message_id: int) -> None:
        payload = {
            "chat_id": settings.PUBLIC_CHANNEL_ID,
            "text": self._build_public_post_text(),
            "reply_parameters": {
                "message_id": telegram_message_id,
                "chat_id": settings.MAIN_CHANNEL_ID,
            },
        }
        result = await sender_bot.send_request("sendMessage", payload)
        if not result.success:
            logger.error(f"Public Send Failed: {result.error_message}")
            raise Exception(f"Failed to send public post: {result.error_message}")

    async def _send_user_post_in_hilfen_channel(self, telegram_message_id: int) -> None:
        payload = {
            "chat_id": settings.HILFEN_CHANNEL_ID,
            "text": self._build_hilfen_post_text(),
            "reply_parameters": {
                "message_id": telegram_message_id,
                "chat_id": settings.MAIN_CHANNEL_ID,
            },
        }
        result = await sender_bot.send_request("sendMessage", payload)
        if not result.success:
            logger.error(f"Hilfen Send Failed: {result.error_message}")
            raise Exception(f"Failed to send hilfen post: {result.error_message}")

    async def _send_user_post_in_admin_channel(self, telegram_message_id: int) -> None:
        payload = {
            "chat_id": settings.ADMIN_CHANNEL_ID,   # ensure this setting exists
            "text": self._build_admin_post_text(),
            "reply_parameters": {
                "message_id": telegram_message_id,
                "chat_id": settings.MAIN_CHANNEL_ID,
            },
        }
        result = await sender_bot.send_request("sendMessage", payload)
        if not result.success:
            logger.error(f"Admin Send Failed: {result.error_message}")
            raise Exception(f"Failed to send admin post: {result.error_message}")

    # --- Confirmation (polling) helpers ---

    async def _confirm_group_message(self, user_id: int) -> User:
        return await self._confirm_field(user_id, "group_message_id", "Main")

    async def _confirm_public_group_post(self, user_id: int) -> User:
        return await self._confirm_field(user_id, "public_group_message_id", "Public")

    async def _confirm_hilfen_group_post(self, user_id: int) -> User:
        return await self._confirm_field(user_id, "hilfen_group_message_id", "Hilfen")

    async def _confirm_admin_group_post(self, user_id: int) -> User:
        return await self._confirm_field(user_id, "admin_group_message_id", "Admin")

    async def _confirm_field(self, user_id: int, field: str, label: str) -> User:
        start_time = datetime.now()
        timeout = 45
        while (datetime.now() - start_time).total_seconds() < timeout:
            await self.db.commit()
            user = await self.repo.get_fresh_by_id(user_id)
            if user and getattr(user, field, None) is not None:
                logger.info(f"{label} group message confirmed for {user_id}: {getattr(user, field)}")
                return user
            await asyncio.sleep(5)
        logger.error(f"Timeout waiting for {label} group_message_id for user {user_id}")
        raise Exception(f"Timed out waiting for {label} Group Message ID")