# app/modules/hilfen/handlers/stateful/house_news_flow_handlers.py
"""
Handlers for the House News creation flow – city selection & description.
"""

import logging
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.hilfen.core.base_handler import BaseHandler
from app.modules.hilfen.core.scenarios import is_user_message_in_private
from app.modules.hilfen.constants import (
    CANCEL_PREFIX,
    ANOTHER_CITY_BUTTON_TEXT,
    CITY_FLAG,
)
from app.modules.hilfen.repositories.bot_state import BotStateRepository
from app.modules.hilfen.repositories.news_repository import NewsRepository
from app.modules.hilfen.services.state_service import BotStateService
from app.modules.hilfen.services.telegram_service import (
    send_message_with_keyboard,
    send_message,
)
from app.modules.hilfen.services.keyboard_service import (
    get_main_menu_keyboard,
    build_city_keyboard,
    build_cancel_keyboard,
)
from app.modules.hilfen.services.city_service import get_all_cities, is_valid_city

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Utility: return to main menu (resets state, sends main keyboard)
# ---------------------------------------------------------------------------
async def _go_main_menu(
    db: AsyncSession, user_id: int, chat_id: int, text: str
) -> None:
    state_repo = BotStateRepository(db)
    state_service = BotStateService(state_repo)
    await state_service.update_user_state(user_id, None)
    await send_message_with_keyboard(chat_id, text, get_main_menu_keyboard())


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
    Inserts a news row and moves to description state.
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

        # Extract city name from "🇩🇪 Berlin"
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
            news_type="house",
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
            user_id, f"news_house_description+{news_id}"
        )

        keyboard = build_cancel_keyboard()
        await send_message_with_keyboard(
            chat_id,
            "✅ City saved. Now please send the description of your house:",
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
    """Accept any free‑form text as the custom city name and create news row."""

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
            news_type="house",
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
            user_id, f"news_house_description+{news_id}"
        )

        keyboard = build_cancel_keyboard()
        await send_message_with_keyboard(
            chat_id,
            f"✅ City '{city_name}' saved. Now please send the description of your house:",
            keyboard,
        )


# ===========================================================================
# DESCRIPTION INPUT (state = "news_house_description+<newsid>")
# ===========================================================================

def _extract_newsid(state: str) -> int | None:
    """Extract integer news id from state string like 'news_house_description+123'."""
    try:
        parts = state.split("+", 1)
        if len(parts) != 2:
            logger.warning(f"Invalid state format (no '+'): {state}")
            return None
        value = parts[1]
        news_id = int(value)
        if not isinstance(news_id, int):
            logger.warning(f"Extracted news id is not int: {news_id!r}")
            return None
        return news_id
    except (IndexError, ValueError) as e:
        logger.warning(f"Failed to extract news id from state {state!r}: {e}")
        return None


class HouseNewsDescriptionCancelHandler(BaseHandler):
    """Cancel during description input – delete the news row and return to menu."""

    async def match(self, context: dict, db: AsyncSession) -> bool:
        state = context.get("user_state")
        # Guard against None or non‑string values before calling .startswith()
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
        else:
            logger.warning("Could not extract news_id from state, skipping delete")

        await _go_main_menu(
            db, context["user_id"], context["chat_id"],
            "❌ House ad creation cancelled.",
        )


class HouseNewsDescriptionInputHandler(BaseHandler):
    """Receive the description text and update the news row."""

    async def match(self, context: dict, db: AsyncSession) -> bool:
        state = context.get("user_state")
        # Guard against None or non‑string values before calling .startswith()
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

        # ---- DIAGNOSTIC LOGGING START ----
        logger.info(f"=== Description handler ===")
        logger.info(f"User ID: {user_id}, Chat ID: {chat_id}")
        logger.info(f"Raw description text: {description!r}")
        logger.info(f"Extracted news_id: {news_id}")
        logger.info(f"Current user_state: {context.get('user_state')}")
        # ---- DIAGNOSTIC LOGGING END ----

        if news_id is None:
            logger.error(f"Failed to extract news_id from state: {context['user_state']}")
            await send_message(chat_id, "⚠️ An error occurred. Please start again.")
            await _go_main_menu(db, user_id, chat_id, "Back to main menu.")
            return

        if not isinstance(news_id, int):
            logger.error(f"Extracted news_id is not int: {news_id!r}")
            await send_message(chat_id, "⚠️ Internal error (invalid news ID). Please start again.")
            await _go_main_menu(db, user_id, chat_id, "Back to main menu.")
            return

        news_repo = NewsRepository(db)

        # Log the exact call arguments before invoking update_news
        logger.info(f"Calling news_repo.update_news with arguments: news_id={news_id}, user_id={user_id}, description={description!r}")

        try:
            await news_repo.update_news(news_id=news_id, user_id=user_id, news_text=description)
        except RuntimeError as e:
            logger.exception(f"Update failed for user {user_id}, news {news_id}")
            await send_message(
                chat_id,
                "❌ A database error occurred. Our team has been notified. "
                "Please contact support if the problem persists."
            )
            await _go_main_menu(db, user_id, chat_id, "Back to main menu.")
            return
        except Exception as e:
            logger.exception(f"Unexpected error updating news {news_id}: {e}")
            await send_message(chat_id, "⚠️ Unexpected error. Please try again later.")
            await _go_main_menu(db, user_id, chat_id, "Back to main menu.")
            return

        await send_message(chat_id, "✅ Description saved. (Photo upload will be available soon.)")
        await _go_main_menu(db, user_id, chat_id, "🏠 Main menu")