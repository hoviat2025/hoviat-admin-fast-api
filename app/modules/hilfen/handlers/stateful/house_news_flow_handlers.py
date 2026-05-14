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
    STOP_NEWS_PREFIX,
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
    build_user_stopped_keyboard,
)
from app.modules.hilfen.services.city_service import get_all_cities, is_valid_city
from app.modules.hilfen.services.news_format_service import (
    format_news_preview,
    format_stopped_news,
)

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
            "❌ ایجاد آگهی خانه لغو شد.",
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
            "📍 لطفاً نام شهر خود را تایپ کنید:",
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
                f"❌ '{city_name}' در لیست نیست. لطفاً از کیبورد یکی را انتخاب کنید یا «شهر دیگر» را بزنید.",
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
            await send_message(chat_id, "⚠️ خطای داخلی. لطفاً بعداً دوباره تلاش کنید.")
            await _go_main_menu(db, user_id, chat_id, "بازگشت به منوی اصلی.")
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
            "✅ شهر ذخیره شد. حالا لطفاً نقش خود را انتخاب کنید:",
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
            "❌ ایجاد آگهی خانه لغو شد.",
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
            await send_message(chat_id, "⚠️ خطای داخلی. لطفاً بعداً دوباره تلاش کنید.")
            await _go_main_menu(db, user_id, chat_id, "بازگشت به منوی اصلی.")
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
            f"✅ شهر '{city_name}' ذخیره شد. حالا لطفاً نقش خود را انتخاب کنید:",
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
            "❌ ایجاد آگهی خانه لغو شد.",
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
        await send_message(chat_id, "⚠️ خطا. لطفاً دوباره شروع کنید.")
        await _go_main_menu(db, user_id, chat_id, "منوی اصلی")
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
        "✅ نقش ذخیره شد. حالا لطفاً توضیحات خانه خود را ارسال کنید:",
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
            "⚠️ لطفاً یکی از گزینه‌های زیر را انتخاب کنید:",
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
            "❌ ایجاد آگهی خانه لغو شد.",
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
            await send_message(chat_id, "⚠️ خطایی رخ داد. لطفاً دوباره شروع کنید.")
            await _go_main_menu(db, user_id, chat_id, "بازگشت به منوی اصلی.")
            return

        news_repo = NewsRepository(db)
        try:
            await news_repo.update_news(news_id=news_id, user_id=user_id, news_text=description)
        except Exception as e:
            logger.exception(f"Update failed for user {user_id}, news {news_id}")
            await send_message(
                chat_id,
                "❌ خطای پایگاه داده رخ داد. لطفاً بعداً دوباره تلاش کنید."
            )
            await _go_main_menu(db, user_id, chat_id, "بازگشت به منوی اصلی.")
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
            "🖼️ اگر تمایل دارید می توانید برای آگهی یک یا چند عکس بفرستید"
            "یا این مرحله را رد کنید:",
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
            "❌ ایجاد آگهی خانه لغو شد.",
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
            await send_message(chat_id, "⚠️ خطا. لطفاً دوباره شروع کنید.")
            await _go_main_menu(db, user_id, chat_id, "منوی اصلی")
            return

        news_repo = NewsRepository(db)
        news = await news_repo.get_by_id(news_id)
        if not news:
            await send_message(chat_id, "⚠️ آگهی یافت نشد. لطفاً دوباره شروع کنید.")
            await _go_main_menu(db, user_id, chat_id, "منوی اصلی")
            return

        preview_text = format_news_preview(news.city, news.news_text or "")

        preview_msg_id = await send_message_return_id(chat_id, preview_text)
        if preview_msg_id is None:
            await send_message(chat_id, "⚠️ پیش‌نمایش ارسال نشد، لطفاً بعداً تلاش کنید.")
            await _go_main_menu(db, user_id, chat_id, "منوی اصلی")
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
            "🔍 این پیش‌نمایش آگهی شماست. آیا تایید می‌کنید؟",
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
            await send_message(chat_id, "⚠️ خطا. لطفاً دوباره شروع کنید.")
            await _go_main_menu(db, user_id, chat_id, "منوی اصلی")
            return

        news_repo = NewsRepository(db)
        news = await news_repo.get_by_id(news_id)
        if not news:
            await send_message(chat_id, "⚠️ آگهی یافت نشد. لطفاً دوباره شروع کنید.")
            await _go_main_menu(db, user_id, chat_id, "منوی اصلی")
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
            await send_message(chat_id, "⚠️ ارسال پیش‌نمایش ناموفق بود. لطفاً بعداً تلاش کنید.")
            await _go_main_menu(db, user_id, chat_id, "منوی اصلی")
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
            "🔍 این پیش‌نمایش آگهی شماست. آیا تایید می‌کنید؟",
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
            "📎 لطفاً عکس بفرستید (تکی یا آلبوم) یا از دکمه‌های زیر استفاده کنید:\n"
            f"• {SKIP_PHOTOS_BUTTON_TEXT}\n"
            f"• لغو",
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
            await send_message(chat_id, "⚠️ آگهی یافت نشد. لطفاً دوباره شروع کنید.")
            await _go_main_menu(db, user_id, chat_id, "منوی اصلی")
            return

        # ------------------------------------------------
        # 1. Edit the user's inline‑keyboard message
        # ------------------------------------------------
        if news.user_handle_message_id:
            await edit_message_text(
                chat_id, news.user_handle_message_id,
                "✅ آگهی شما برای بررسی ارسال شد."
            )
            await edit_message_reply_markup(
                chat_id, news.user_handle_message_id,
                reply_markup={"inline_keyboard": []}
            )
        else:
            await send_message(chat_id, "✅ آگهی شما برای بررسی ارسال شد.")

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
            await send_message(chat_id, "⚠️ خطای پیکربندی. لطفاً با پشتیبانی تماس بگیرید.")
            await _go_main_menu(db, user_id, chat_id, "منوی اصلی")
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
            await send_message(chat_id, "⚠️ ارسال برای بررسی ناموفق بود، لطفاً بعداً تلاش کنید.")
            await _go_main_menu(db, user_id, chat_id, "منوی اصلی")
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
            "📬 **آگهی جدید خانه برای بررسی**\nلطفاً تایید یا رد کنید:",
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
        await _go_main_menu(db, user_id, chat_id, "🏠 منوی اصلی")

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
            await _go_main_menu(db, user_id, chat_id, "🏠 منوی اصلی")
            return

        if news.user_handle_message_id:
            await edit_message_text(
                chat_id, news.user_handle_message_id,
                "❌ آگهی لغو شد."
            )
            await edit_message_reply_markup(
                chat_id, news.user_handle_message_id,
                reply_markup={"inline_keyboard": []}
            )
        else:
            await send_message(chat_id, "❌ آگهی لغو شد.")

        try:
            await news_repo.delete_news(cb_news_id)
        except Exception as e:
            logger.error(f"Error deleting news {cb_news_id}: {e}")

        await _go_main_menu(db, user_id, chat_id, "🏠 منوی اصلی")


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
                "⚠️ لطفاً برای تایید یا رد پیش‌نمایش از دکمه‌های بالا استفاده کنید.",
                reply_to_message_id=reply_to,
            )
        else:
            await send_message(
                chat_id,
                "⚠️ لطفاً برای تایید یا رد پیش‌نمایش از دکمه‌ها استفاده کنید.",
            )


# ===========================================================================
# STOP THE NEWS (callback data = stop_news_<type>_<newsid>)
# ===========================================================================
class HouseNewsStopCallbackHandler(BaseHandler):
    """User clicked the 'Stop the news' button on a published ad."""

    async def match(self, context: dict, db: AsyncSession) -> bool:
        if context.get("update_type") != "callback_query":
            return False
        # Only in private chat
        if not is_user_message_in_private(context):
            return False
        data = context.get("text", "")
        return data.startswith(STOP_NEWS_PREFIX)

    async def handle(self, context: dict, db: AsyncSession) -> None:
        data = context["text"]
        chat_id = context["chat_id"]          # user's private chat
        user_id = context["user_id"]

        # Extract news id from callback data (format: stop_news_<type>_<id>)
        try:
            news_id = int(data.rsplit("_", 1)[-1])
        except (ValueError, IndexError):
            logger.warning(f"Invalid stop callback data: {data}")
            return

        news_repo = NewsRepository(db)
        news = await news_repo.get_by_id(news_id)
        if not news or news.status != "published":
            # Already stopped or never published – nothing to do
            await send_message(chat_id, "⚠️ این آگهی دیگر فعال نیست.")
            return

        # 1) Mark as stopped in the database
        await news_repo.update_news(news_id=news_id, status="stopped")

        # 2) Edit the published post in the target channel
        if news.main_channel_id and news.main_channel_message_id:
            stopped_text = format_stopped_news(news.news_text or "")
            await edit_message_text(
                news.main_channel_id,
                news.main_channel_message_id,
                stopped_text,
            )

        # 3) Edit the contact comment under the post (remove personal link)
        if news.group_chat_id and news.contact_group_message_id:
            await edit_message_text(
                news.group_chat_id,
                news.contact_group_message_id,
                "⛔️ این آگهی متوقف شده است. لطفاً به پست اصلی بالا مراجعه کنید.",
            )

        # 4) Edit the user’s handler message (keep only the “View my ad” button)
        if news.user_id and news.user_handle_message_id:
            # Rebuild the post URL (same logic as in admin confirm)
            channel_id_str = str(news.main_channel_id).removeprefix("-100")
            post_url = f"https://t.me/c/{channel_id_str}/{news.main_channel_message_id}"

            new_keyboard = build_user_stopped_keyboard(post_url)
            await edit_message_reply_markup(
                news.user_id,
                news.user_handle_message_id,
                reply_markup={"inline_keyboard": new_keyboard},
            )