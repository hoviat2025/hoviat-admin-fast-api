# app/modules/hilfen/handlers/stateful/house_news_flow_handlers.py
"""
Handlers for the House News creation flow:
  city → role → description → photos → preview → confirm/decline
"""

import json
import logging
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.modules.hilfen.core.base_handler import BaseHandler
from app.modules.hilfen.core.scenarios import is_user_message_in_private
from app.modules.hilfen.constants import (
    CANCEL_PREFIX,
    ANOTHER_CITY_BUTTON_TEXT,
    CITY_FLAG,
    SKIP_PHOTOS_BUTTON_TEXT,
    ROLE_RENT_TEXT,
    ROLE_PUBLISH_TEXT,
    HOUSE_PREVIEW_CONFIRM_PREFIX,
    HOUSE_PREVIEW_DECLINE_PREFIX,
)
from app.modules.hilfen.repositories.bot_state import BotStateRepository
from app.modules.hilfen.repositories.news_repository import NewsRepository
from app.modules.hilfen.services.state_service import BotStateService
from app.modules.hilfen.services.telegram_service import (
    send_message_with_keyboard,
    send_message,
    send_photo,
    send_media_group,
    send_message_with_inline_keyboard,
    send_message_return_id,
    send_message_with_reply,
    edit_message_text,
    edit_message_reply_markup,
)
from app.modules.hilfen.services.keyboard_service import (
    get_main_menu_keyboard,
    build_city_keyboard,
    build_cancel_keyboard,
    build_role_keyboard,
    build_photos_keyboard,
    build_preview_confirm_keyboard,
    build_admin_review_keyboard,

)
from app.modules.hilfen.services.city_service import get_all_cities, is_valid_city
from app.modules.hilfen.services.news_format_service import format_news_preview

from app.modules.hilfen.services.reply_service import ReplyService


logger = logging.getLogger(__name__)

NEWS_TYPE = "house"


# ---------------------------------------------------------------------------
# Utility: return to main menu
# ---------------------------------------------------------------------------
async def _go_main_menu(
    db: AsyncSession, user_id: int, chat_id: int, text: str
) -> None:
    state_repo = BotStateRepository(db)
    state_service = BotStateService(state_repo)
    await state_service.update_user_state(user_id, None)
    await send_message_with_keyboard(chat_id, text, get_main_menu_keyboard())


def _extract_newsid(state: str) -> int | None:
    """Extract integer news id from state string like 'news_house_role+123'."""
    try:
        parts = state.split("+", 1)
        if len(parts) != 2:
            logger.warning(f"Invalid state format (no '+'): {state}")
            return None
        value = parts[1]
        news_id = int(value)
        return news_id
    except (IndexError, ValueError) as e:
        logger.warning(f"Failed to extract news id from state {state!r}: {e}")
        return None


# ===========================================================================
# CITY SELECTION (state = "news_house_city")
# ===========================================================================

class HouseCityCancelHandler(BaseHandler):
    """Cancel during city selection – return to main menu."""

    async def match(self, context: dict, db: AsyncSession) -> bool:
        return (
            context.get("user_state") == "news_house_city"
            and is_user_message_in_private(context)
            and context.get("update_type") == "message"
            and context.get("text", "").startswith(CANCEL_PREFIX)
        )

    async def handle(self, context: dict, db: AsyncSession) -> None:
        await _go_main_menu(
            db, context["user_id"], context["chat_id"],
            "❌ House ad creation cancelled.",
        )


class HouseCityAnotherCityHandler(BaseHandler):
    """User wants to type a custom city."""

    async def match(self, context: dict, db: AsyncSession) -> bool:
        return (
            context.get("user_state") == "news_house_city"
            and is_user_message_in_private(context)
            and context.get("update_type") == "message"
            and context.get("text") == ANOTHER_CITY_BUTTON_TEXT
        )

    async def handle(self, context: dict, db: AsyncSession) -> None:
        user_id = context["user_id"]
        chat_id = context["chat_id"]

        state_repo = BotStateRepository(db)
        state_service = BotStateService(state_repo)
        await state_service.update_user_state(user_id, "news_house_city_custom")

        keyboard = build_cancel_keyboard()
        await send_message_with_keyboard(
            chat_id,
            "📍 Please type the name of your city:",
            keyboard,
        )


class HouseCityInputHandler(BaseHandler):
    """
    Handle a city button tap or typed city name while in "news_house_city".
    Creates a news row and moves to the role step.
    """

    async def match(self, context: dict, db: AsyncSession) -> bool:
        return (
            context.get("user_state") == "news_house_city"
            and is_user_message_in_private(context)
            and context.get("update_type") == "message"
        )

    async def handle(self, context: dict, db: AsyncSession) -> None:
        raw_text = context["text"]
        chat_id = context["chat_id"]
        user_id = context["user_id"]

        city_name = raw_text
        if raw_text.startswith(f"{CITY_FLAG} "):
            city_name = raw_text[len(CITY_FLAG) + 1 :].strip()

        if not is_valid_city(city_name):
            cities = get_all_cities()
            keyboard = build_city_keyboard(cities)
            await send_message_with_keyboard(
                chat_id,
                f"❌ '{city_name}' is not in the list. Please choose from the keyboard or use 'Another City'.",
                keyboard,
            )
            return

        news_repo = NewsRepository(db)
        news = await news_repo.create_news(
            user_id=user_id,
            news_type=NEWS_TYPE,
            city=city_name,
            status="draft",
        )

        if not isinstance(news.id, int):
            logger.error(f"Created news has non-int id: {news.id!r}")
            await send_message(chat_id, "⚠️ Internal error. Please try again later.")
            await _go_main_menu(db, user_id, chat_id, "Back to main menu.")
            return

        news_id = news.id
        state_repo = BotStateRepository(db)
        state_service = BotStateService(state_repo)
        await state_service.update_user_state(
            user_id, f"news_house_role+{news_id}"
        )

        keyboard = build_role_keyboard()
        await send_message_with_keyboard(
            chat_id,
            "✅ City saved. Now please choose your role:",
            keyboard,
        )


# ===========================================================================
# CUSTOM CITY FLOW (state = "news_house_city_custom")
# ===========================================================================

class HouseCityCustomCancelHandler(BaseHandler):
    """Cancel while typing a custom city."""

    async def match(self, context: dict, db: AsyncSession) -> bool:
        return (
            context.get("user_state") == "news_house_city_custom"
            and is_user_message_in_private(context)
            and context.get("update_type") == "message"
            and context.get("text", "").startswith(CANCEL_PREFIX)
        )

    async def handle(self, context: dict, db: AsyncSession) -> None:
        await _go_main_menu(
            db, context["user_id"], context["chat_id"],
            "❌ House ad creation cancelled.",
        )


class HouseCityCustomInputHandler(BaseHandler):
    """Accept any free‑form text as the custom city name and move to role step."""

    async def match(self, context: dict, db: AsyncSession) -> bool:
        return (
            context.get("user_state") == "news_house_city_custom"
            and is_user_message_in_private(context)
            and context.get("update_type") == "message"
        )

    async def handle(self, context: dict, db: AsyncSession) -> None:
        city_name = context["text"].strip()
        chat_id = context["chat_id"]
        user_id = context["user_id"]

        news_repo = NewsRepository(db)
        news = await news_repo.create_news(
            user_id=user_id,
            news_type=NEWS_TYPE,
            city=city_name,
            status="draft",
        )

        if not isinstance(news.id, int):
            logger.error(f"Created news has non-int id: {news.id!r}")
            await send_message(chat_id, "⚠️ Internal error. Please try again later.")
            await _go_main_menu(db, user_id, chat_id, "Back to main menu.")
            return

        news_id = news.id
        state_repo = BotStateRepository(db)
        state_service = BotStateService(state_repo)
        await state_service.update_user_state(
            user_id, f"news_house_role+{news_id}"
        )

        keyboard = build_role_keyboard()
        await send_message_with_keyboard(
            chat_id,
            f"✅ City '{city_name}' saved. Now please choose your role:",
            keyboard,
        )


# ===========================================================================
# ROLE SELECTION (state = "news_house_role+<newsid>")
# ===========================================================================

class HouseNewsRoleCancelHandler(BaseHandler):
    """Cancel during role selection – delete the news row and return to menu."""

    async def match(self, context: dict, db: AsyncSession) -> bool:
        state = context.get("user_state")
        if not isinstance(state, str) or not state.startswith("news_house_role+"):
            return False
        if not is_user_message_in_private(context):
            return False
        if context.get("update_type") != "message":
            return False
        text = context.get("text")
        if not isinstance(text, str):
            return False
        return text.startswith(CANCEL_PREFIX)

    async def handle(self, context: dict, db: AsyncSession) -> None:
        news_id = _extract_newsid(context["user_state"])
        if news_id is not None:
            try:
                news_repo = NewsRepository(db)
                await news_repo.delete_news(news_id)
            except Exception as e:
                logger.error(f"Error deleting news {news_id}: {e}")
        await _go_main_menu(
            db, context["user_id"], context["chat_id"],
            "❌ House ad creation cancelled.",
        )


class HouseNewsRoleRentHandler(BaseHandler):
    """User selects 'I want to rent'."""

    async def match(self, context: dict, db: AsyncSession) -> bool:
        state = context.get("user_state")
        if not isinstance(state, str) or not state.startswith("news_house_role+"):
            return False
        if not is_user_message_in_private(context):
            return False
        if context.get("update_type") != "message":
            return False
        text = context.get("text")
        return text == ROLE_RENT_TEXT

    async def handle(self, context: dict, db: AsyncSession) -> None:
        await _handle_role_selection(context, db, "rent")


class HouseNewsRolePublishHandler(BaseHandler):
    """User selects 'I want to publish for renting'."""

    async def match(self, context: dict, db: AsyncSession) -> bool:
        state = context.get("user_state")
        if not isinstance(state, str) or not state.startswith("news_house_role+"):
            return False
        if not is_user_message_in_private(context):
            return False
        if context.get("update_type") != "message":
            return False
        text = context.get("text")
        return text == ROLE_PUBLISH_TEXT

    async def handle(self, context: dict, db: AsyncSession) -> None:
        await _handle_role_selection(context, db, "publish")


async def _handle_role_selection(context: dict, db: AsyncSession, sub_type: str) -> None:
    """Common logic for storing the chosen role and advancing to description."""
    news_id = _extract_newsid(context["user_state"])
    chat_id = context["chat_id"]
    user_id = context["user_id"]

    if news_id is None:
        await send_message(chat_id, "⚠️ Error. Please start again.")
        await _go_main_menu(db, user_id, chat_id, "Main menu")
        return

    news_repo = NewsRepository(db)
    await news_repo.update_news(news_id=news_id, sub_type=sub_type)

    state_repo = BotStateRepository(db)
    state_service = BotStateService(state_repo)
    await state_service.update_user_state(
        user_id, f"news_house_description+{news_id}"
    )

    keyboard = build_cancel_keyboard()
    await send_message_with_keyboard(
        chat_id,
        f"✅ Role saved. Now please send the description of your house:",
        keyboard,
    )


class HouseNewsRoleInvalidHandler(BaseHandler):
    """Any other text during role selection – reminder."""

    async def match(self, context: dict, db: AsyncSession) -> bool:
        state = context.get("user_state")
        if not isinstance(state, str) or not state.startswith("news_house_role+"):
            return False
        if not is_user_message_in_private(context):
            return False
        if context.get("update_type") != "message":
            return False
        text = context.get("text")
        if not isinstance(text, str):
            return False
        # Skip specific buttons already caught
        if text in (ROLE_RENT_TEXT, ROLE_PUBLISH_TEXT) or text.startswith(CANCEL_PREFIX):
            return False
        return True

    async def handle(self, context: dict, db: AsyncSession) -> None:
        await send_message(
            context["chat_id"],
            "⚠️ Please choose one of the options below:",
        )


# ===========================================================================
# DESCRIPTION INPUT (state = "news_house_description+<newsid>")
# ===========================================================================

class HouseNewsDescriptionCancelHandler(BaseHandler):
    """Cancel during description input – delete the news row and return to menu."""

    async def match(self, context: dict, db: AsyncSession) -> bool:
        state = context.get("user_state")
        if not isinstance(state, str):
            return False
        return (
            state.startswith("news_house_description+")
            and is_user_message_in_private(context)
            and context.get("update_type") == "message"
            and context.get("text", "").startswith(CANCEL_PREFIX)
        )

    async def handle(self, context: dict, db: AsyncSession) -> None:
        news_id = _extract_newsid(context["user_state"])
        if news_id is not None:
            try:
                news_repo = NewsRepository(db)
                await news_repo.delete_news(news_id)
            except Exception as e:
                logger.error(f"Error deleting news {news_id}: {e}")
        await _go_main_menu(
            db, context["user_id"], context["chat_id"],
            "❌ House ad creation cancelled.",
        )


class HouseNewsDescriptionInputHandler(BaseHandler):
    """Receive the description text and advance to photo step."""

    async def match(self, context: dict, db: AsyncSession) -> bool:
        state = context.get("user_state")
        if not isinstance(state, str):
            return False
        return (
            state.startswith("news_house_description+")
            and is_user_message_in_private(context)
            and context.get("update_type") == "message"
        )

    async def handle(self, context: dict, db: AsyncSession) -> None:
        description = context["text"]
        chat_id = context["chat_id"]
        user_id = context["user_id"]
        news_id = _extract_newsid(context["user_state"])

        if news_id is None:
            await send_message(chat_id, "⚠️ An error occurred. Please start again.")
            await _go_main_menu(db, user_id, chat_id, "Back to main menu.")
            return

        news_repo = NewsRepository(db)
        try:
            await news_repo.update_news(news_id=news_id, user_id=user_id, news_text=description)
        except Exception as e:
            logger.exception(f"Update failed for user {user_id}, news {news_id}")
            await send_message(
                chat_id,
                "❌ A database error occurred. Please try again later."
            )
            await _go_main_menu(db, user_id, chat_id, "Back to main menu.")
            return

        # Move to photo step
        state_repo = BotStateRepository(db)
        state_service = BotStateService(state_repo)
        await state_service.update_user_state(
            user_id, f"news_house_photos+{news_id}"
        )

        keyboard = build_photos_keyboard()
        await send_message_with_keyboard(
            chat_id,
            "🖼️ Now you can send one or more photos of your house "
            "(as an album or single photo), or skip this step:",
            keyboard,
        )


# ===========================================================================
# PHOTOS STEP (state = "news_house_photos+<newsid>")
# ===========================================================================

class HouseNewsPhotosCancelHandler(BaseHandler):
    """Cancel during photo upload – delete news row and return to menu."""

    async def match(self, context: dict, db: AsyncSession) -> bool:
        state = context.get("user_state")
        if not isinstance(state, str) or not state.startswith("news_house_photos+"):
            return False
        if not is_user_message_in_private(context):
            return False
        if context.get("update_type") != "message":
            return False
        text = context.get("text")
        if not isinstance(text, str):
            return False
        return text.startswith(CANCEL_PREFIX)

    async def handle(self, context: dict, db: AsyncSession) -> None:
        news_id = _extract_newsid(context["user_state"])
        if news_id is not None:
            try:
                news_repo = NewsRepository(db)
                await news_repo.delete_news(news_id)
            except Exception as e:
                logger.error(f"Error deleting news {news_id}: {e}")
        await _go_main_menu(
            db, context["user_id"], context["chat_id"],
            "❌ House ad creation cancelled.",
        )


class HouseNewsPhotosSkipHandler(BaseHandler):
    """User chooses not to send photos – proceed to preview."""

    async def match(self, context: dict, db: AsyncSession) -> bool:
        state = context.get("user_state")
        if not isinstance(state, str) or not state.startswith("news_house_photos+"):
            return False
        if not is_user_message_in_private(context):
            return False
        if context.get("update_type") != "message":
            return False
        text = context.get("text")
        if not isinstance(text, str):
            return False
        return text == SKIP_PHOTOS_BUTTON_TEXT

    async def handle(self, context: dict, db: AsyncSession) -> None:
        news_id = _extract_newsid(context["user_state"])
        chat_id = context["chat_id"]
        user_id = context["user_id"]

        if news_id is None:
            await send_message(chat_id, "⚠️ Error. Please start again.")
            await _go_main_menu(db, user_id, chat_id, "Main menu")
            return

        news_repo = NewsRepository(db)
        news = await news_repo.get_by_id(news_id)
        if not news:
            await send_message(chat_id, "⚠️ News not found. Please start again.")
            await _go_main_menu(db, user_id, chat_id, "Main menu")
            return

        preview_text = format_news_preview(news.city, news.news_text or "")

        preview_msg_id = await send_message_return_id(chat_id, preview_text)
        if preview_msg_id is None:
            await send_message(chat_id, "⚠️ Could not send preview, please try again later.")
            await _go_main_menu(db, user_id, chat_id, "Main menu")
            return

        await news_repo.update_news(news_id=news_id, preview_message_id=preview_msg_id)

        state_repo = BotStateRepository(db)
        state_service = BotStateService(state_repo)
        await state_service.update_user_state(
            user_id, f"news_house_preview+{news_id}"
        )

        inline_kb = build_preview_confirm_keyboard(NEWS_TYPE, news_id)
        handle_msg_id = await send_message_with_inline_keyboard(
            chat_id,
            "🔍 This is the preview of your news. Do you confirm?",
            inline_kb,
            reply_to_message_id=preview_msg_id,
        )
        if handle_msg_id is not None:
            await news_repo.update_news(news_id=news_id, user_handle_message_id=handle_msg_id)


class HouseNewsPhotosMediaHandler(BaseHandler):
    """Handle a single photo or an album – store media and send preview."""

    async def match(self, context: dict, db: AsyncSession) -> bool:
        state = context.get("user_state")
        if not isinstance(state, str) or not state.startswith("news_house_photos+"):
            return False
        if not is_user_message_in_private(context):
            return False
        if context.get("update_type") not in ("message", "edited_message"):
            return False
        return (
            context.get("photo") is not None
            or context.get("album_photos") is not None
        )

    async def handle(self, context: dict, db: AsyncSession) -> None:
        news_id = _extract_newsid(context["user_state"])
        chat_id = context["chat_id"]
        user_id = context["user_id"]

        if news_id is None:
            await send_message(chat_id, "⚠️ Error. Please start again.")
            await _go_main_menu(db, user_id, chat_id, "Main menu")
            return

        news_repo = NewsRepository(db)
        news = await news_repo.get_by_id(news_id)
        if not news:
            await send_message(chat_id, "⚠️ News not found. Please start again.")
            await _go_main_menu(db, user_id, chat_id, "Main menu")
            return

        media_objects = []
        if context.get("album_photos"):
            for photo_array in context["album_photos"]:
                if photo_array:
                    largest = photo_array[-1]
                    media_objects.append({
                        "file_id": largest["file_id"],
                        "file_unique_id": largest["file_unique_id"],
                    })
        else:
            photo_array = context["photo"]
            largest = photo_array[-1]
            media_objects.append({
                "file_id": largest["file_id"],
                "file_unique_id": largest["file_unique_id"],
            })

        media_group_id = context.get("media_group_id")

        await news_repo.update_news(
            news_id=news_id,
            media=json.dumps(media_objects),
            media_group_id=media_group_id,
        )

        preview_text = format_news_preview(news.city, news.news_text or "")

        preview_msg_ids = []
        if len(media_objects) == 1:
            msg_result = await send_photo(chat_id, media_objects[0]["file_id"], caption=preview_text)
            if msg_result:
                preview_msg_ids.append(msg_result["message_id"])
        else:
            media_list = [{"type": "photo", "media": obj["file_id"]} for obj in media_objects]
            msg_results = await send_media_group(chat_id, media_list, caption=preview_text)
            if msg_results:
                preview_msg_ids = [m["message_id"] for m in msg_results]

        if not preview_msg_ids:
            await send_message(chat_id, "⚠️ Failed to send preview. Please try again later.")
            await _go_main_menu(db, user_id, chat_id, "Main menu")
            return

        preview_msg_id = preview_msg_ids[0]
        await news_repo.update_news(news_id=news_id, preview_message_id=preview_msg_id)

        state_repo = BotStateRepository(db)
        state_service = BotStateService(state_repo)
        await state_service.update_user_state(
            user_id, f"news_house_preview+{news_id}"
        )

        inline_kb = build_preview_confirm_keyboard(NEWS_TYPE, news_id)
        handle_msg_id = await send_message_with_inline_keyboard(
            chat_id,
            "🔍 This is the preview of your news. Do you confirm?",
            inline_kb,
            reply_to_message_id=preview_msg_id,
        )
        if handle_msg_id is not None:
            await news_repo.update_news(news_id=news_id, user_handle_message_id=handle_msg_id)


class HouseNewsPhotosInvalidHandler(BaseHandler):
    """Any other input during photo step – reminder."""

    async def match(self, context: dict, db: AsyncSession) -> bool:
        state = context.get("user_state")
        if not isinstance(state, str) or not state.startswith("news_house_photos+"):
            return False
        if not is_user_message_in_private(context):
            return False
        if context.get("update_type") != "message":
            return False
        text = context.get("text")
        if not isinstance(text, str):
            return False
        if text.startswith(CANCEL_PREFIX) or text == SKIP_PHOTOS_BUTTON_TEXT:
            return False
        return True

    async def handle(self, context: dict, db: AsyncSession) -> None:
        await send_message(
            context["chat_id"],
            "📎 Please send photos (single or album), or use the buttons below:\n"
            f"• {SKIP_PHOTOS_BUTTON_TEXT}\n"
            f"• Cancel",
        )


# ===========================================================================
# PREVIEW CONFIRM / DECLINE (state = "news_house_preview+<newsid>")
# ===========================================================================
class HouseNewsPreviewConfirmHandler(BaseHandler):
    """User confirms the preview – send to admin channel with cross‑chat reply, then reply with handler message."""

    async def match(self, context: dict, db: AsyncSession) -> bool:
        if context.get("update_type") != "callback_query":
            return False
        state = context.get("user_state")
        if not isinstance(state, str) or not state.startswith("news_house_preview+"):
            return False
        data = context.get("text", "")
        return data.startswith(HOUSE_PREVIEW_CONFIRM_PREFIX)

    async def handle(self, context: dict, db: AsyncSession) -> None:
        user_id = context["user_id"]
        chat_id = context["chat_id"]
        callback_data = context["text"]
        state_news_id = _extract_newsid(context["user_state"])

        try:
            cb_news_id = int(callback_data[len(HOUSE_PREVIEW_CONFIRM_PREFIX):])
        except ValueError:
            logger.warning(f"Invalid confirm callback data: {callback_data}")
            return

        if state_news_id != cb_news_id:
            logger.warning(f"Mismatch news ids in preview confirm: state={state_news_id}, cb={cb_news_id}")
            return

        news_repo = NewsRepository(db)
        news = await news_repo.get_by_id(cb_news_id)
        if not news:
            await send_message(chat_id, "⚠️ News not found. Please start again.")
            await _go_main_menu(db, user_id, chat_id, "Main menu")
            return

        # ------------------------------------------------
        # 1. Edit the user's inline‑keyboard message
        # ------------------------------------------------
        if news.user_handle_message_id:
            await edit_message_text(
                chat_id, news.user_handle_message_id,
                "✅ Your news has been submitted for review."
            )
            await edit_message_reply_markup(
                chat_id, news.user_handle_message_id,
                reply_markup={"inline_keyboard": []}
            )
        else:
            await send_message(chat_id, "✅ Your news has been submitted for review.")

        # ------------------------------------------------
        # 2. Build the cross‑chat reply for the admin channel
        # ------------------------------------------------
        reply_service = ReplyService(db)
        reply_params = await reply_service.build_admin_channel_reply(user_id)

        # ------------------------------------------------
        # 3. Forward the preview to the check‑admin channel
        # ------------------------------------------------
        preview_text = format_news_preview(news.city, news.news_text or "")
        media_objects = None
        if news.media:
            try:
                media_objects = json.loads(news.media)
            except Exception:
                logger.warning(f"Invalid media JSON for news {news.id}")

        try:
            check_admin_channel = int(settings.CHECK_ADMIN_CHANNEL_ID)
        except (ValueError, TypeError):
            logger.error("CHECK_ADMIN_CHANNEL_ID is not a valid integer")
            await send_message(chat_id, "⚠️ Configuration error. Please contact support.")
            await _go_main_menu(db, user_id, chat_id, "Main menu")
            return

        admin_msg_id = None
        if media_objects and len(media_objects) > 0:
            if len(media_objects) == 1:
                result = await send_photo(
                    check_admin_channel,
                    media_objects[0]["file_id"],
                    caption=preview_text,
                    reply_parameters=reply_params,          # <-- cross‑chat reply
                )
                if result:
                    admin_msg_id = result["message_id"]
            else:
                media_list = [
                    {"type": "photo", "media": obj["file_id"]} for obj in media_objects
                ]
                results = await send_media_group(
                    check_admin_channel,
                    media_list,
                    caption=preview_text,
                    reply_parameters=reply_params,          # <-- cross‑chat reply
                )
                if results:
                    # The caption is on the first message of the album
                    admin_msg_id = results[0]["message_id"]
        else:
            admin_msg_id = await send_message_return_id(
                check_admin_channel,
                preview_text,
                reply_parameters=reply_params,               # <-- cross‑chat reply
            )

        if admin_msg_id is None:
            await send_message(chat_id, "⚠️ Could not forward to review, please try again later.")
            await _go_main_menu(db, user_id, chat_id, "Main menu")
            return

        # Save the preview message ID (same as before)
        await news_repo.update_news(
            news_id=cb_news_id,
            admin_check_message_id=admin_msg_id,
            admin_check_chat_id=check_admin_channel,
            status="pending",
        )

        # ------------------------------------------------
        # 4. Reply to the preview with the handler message
        # ------------------------------------------------
        admin_kb = build_admin_review_keyboard(cb_news_id)
        handler_msg_id = await send_message_with_inline_keyboard(
            check_admin_channel,
            "📬 **New house ad for review**\nPlease confirm or decline:",
            admin_kb,
            reply_to_message_id=admin_msg_id,   # reply in the same chat
        )
        if handler_msg_id is not None:
            await news_repo.update_news(
                news_id=cb_news_id,
                admin_handler_message_id=handler_msg_id,
            )

        # ------------------------------------------------
        # 5. Return the user to the main menu
        # ------------------------------------------------
        await _go_main_menu(db, user_id, chat_id, "🏠 Main menu")

class HouseNewsPreviewDeclineHandler(BaseHandler):
    """User declines the preview – delete news, edit the inline‑keyboard message, clean up."""

    async def match(self, context: dict, db: AsyncSession) -> bool:
        if context.get("update_type") != "callback_query":
            return False
        state = context.get("user_state")
        if not isinstance(state, str) or not state.startswith("news_house_preview+"):
            return False
        data = context.get("text", "")
        return data.startswith(HOUSE_PREVIEW_DECLINE_PREFIX)

    async def handle(self, context: dict, db: AsyncSession) -> None:
        user_id = context["user_id"]
        chat_id = context["chat_id"]
        callback_data = context["text"]
        state_news_id = _extract_newsid(context["user_state"])

        try:
            cb_news_id = int(callback_data[len(HOUSE_PREVIEW_DECLINE_PREFIX):])
        except ValueError:
            return

        if state_news_id != cb_news_id:
            return

        news_repo = NewsRepository(db)
        news = await news_repo.get_by_id(cb_news_id)
        if not news:
            await _go_main_menu(db, user_id, chat_id, "🏠 Main menu")
            return

        if news.user_handle_message_id:
            await edit_message_text(
                chat_id, news.user_handle_message_id,
                "❌ The news was cancelled."
            )
            await edit_message_reply_markup(
                chat_id, news.user_handle_message_id,
                reply_markup={"inline_keyboard": []}
            )
        else:
            await send_message(chat_id, "❌ The news was cancelled.")

        try:
            await news_repo.delete_news(cb_news_id)
        except Exception as e:
            logger.error(f"Error deleting news {cb_news_id}: {e}")

        await _go_main_menu(db, user_id, chat_id, "🏠 Main menu")


class HouseNewsPreviewFallbackHandler(BaseHandler):
    """Handle random input while in preview state."""

    async def match(self, context: dict, db: AsyncSession) -> bool:
        state = context.get("user_state")
        if not isinstance(state, str) or not state.startswith("news_house_preview+"):
            return False
        return (
            is_user_message_in_private(context)
            and context.get("update_type") in ("message", "callback_query")
        )

    async def handle(self, context: dict, db: AsyncSession) -> None:
        news_id = _extract_newsid(context["user_state"])
        chat_id = context["chat_id"]
        reply_to = None

        if news_id is not None:
            news_repo = NewsRepository(db)
            news = await news_repo.get_by_id(news_id)
            if news and news.user_handle_message_id:
                reply_to = news.user_handle_message_id

        if reply_to:
            await send_message_with_reply(
                chat_id,
                "⚠️ Please use the buttons above to confirm or decline your news preview.",
                reply_to_message_id=reply_to,
            )
        else:
            await send_message(
                chat_id,
                "⚠️ Please use the buttons to confirm or decline your news preview.",
            )