# app/modules/hilfen/handlers/stateful/house_add_flow_handlers.py
"""
Handlers for the house advertisement creation flow.

These run while the user is in 'waiting_to_get_photos_for_house' state.
They accept a single photo or an assembled album, otherwise ask for photos.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.hilfen.core.base_handler import BaseHandler
from app.modules.hilfen.core.scenarios import is_user_message_in_private
from app.modules.hilfen.services.telegram_service import send_message


class HousePhotoHandler(BaseHandler):
    """
    Accepts a single photo or an album when the bot expects house pictures.

    Acknowledges the received file IDs.
    """

    async def match(self, context: dict, db: AsyncSession) -> bool:
        if context.get("user_state") != "waiting_to_get_photos_for_house":
            return False
        if not is_user_message_in_private(context):
            return False

        # Accept messages / edited_messages that contain a photo or are an album composite.
        return (
            context.get("update_type") in ("message", "edited_message")
            and (
                context.get("photo") is not None
                or context.get("album_photos") is not None
            )
        )

    async def handle(self, context: dict, db: AsyncSession) -> None:
        chat_id = context["chat_id"]

        if context.get("album_photos"):
            # Album composite – list of photo arrays
            all_file_ids = []
            for photo_array in context["album_photos"]:
                if photo_array:
                    # The largest thumbnail is the last element
                    file_id = photo_array[-1]["file_id"]
                    all_file_ids.append(file_id)
            msg = (
                f"Received album with {len(all_file_ids)} photos. "
                f"File IDs: {', '.join(all_file_ids)}"
            )
        else:
            # Single photo
            photo_array = context["photo"]
            file_id = photo_array[-1]["file_id"]
            msg = f"Received photo. File ID: {file_id}"

        await send_message(chat_id, msg)


class HouseInvalidInputHandler(BaseHandler):
    """
    Informs the user that the bot expects photos while in the house‑photo state.
    """

    async def match(self, context: dict, db: AsyncSession) -> bool:
        if context.get("user_state") != "waiting_to_get_photos_for_house":
            return False
        if not is_user_message_in_private(context):
            return False

        # Match any message that doesn't contain a photo/album
        return (
            context.get("update_type") in ("message", "edited_message")
            and context.get("photo") is None
            and context.get("album_photos") is None
        )

    async def handle(self, context: dict, db: AsyncSession) -> None:
        await send_message(
            context["chat_id"],
            "Please send photos of your house. I can’t process other input right now."
        )