# app/modules/hilfen/handlers/stateful/house_news_flow_handlers.py
"""
Handlers for the House News creation flow – city selection phase.

This covers:
- Cancelling from the city keyboard
- Selecting "Another City"
- Pressing "Back"
- Receiving a valid city (from the keyboard or typed)
- Handling the subsequent "news_house_city_custom" state (custom city name)
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.hilfen.core.base_handler import BaseHandler
from app.modules.hilfen.core.scenarios import is_user_message_in_private
from app.modules.hilfen.constants import (
    CANCEL_PREFIX,
    BACK_BUTTON_TEXT,
    ANOTHER_CITY_BUTTON_TEXT,
    CITY_FLAG,
)
from app.modules.hilfen.repositories.bot_state import BotStateRepository
from app.modules.hilfen.services.state_service import BotStateService
from app.modules.hilfen.services.telegram_service import (
    send_message_with_keyboard,
    send_message,
    remove_keyboard,
)
from app.modules.hilfen.services.keyboard_service import (
    get_main_menu_keyboard,
    build_city_keyboard,
    build_cancel_back_keyboard,
)
from app.modules.hilfen.services.city_service import get_all_cities, is_valid_city


# ---------------------------------------------------------------------------
# Utility: return to main menu
# ---------------------------------------------------------------------------
async def _return_to_main_menu(
    db: AsyncSession, user_id: int, chat_id: int, text: str
) -> None:
    """Reset state to None and send the main menu keyboard."""
    state_repo = BotStateRepository(db)
    state_service = BotStateService(state_repo)
    await state_service.update_user_state(user_id, None)

    await send_message_with_keyboard(chat_id, text, get_main_menu_keyboard())


# ---------------------------------------------------------------------------
# Cancel handler for state "news_house_city"
# ---------------------------------------------------------------------------
class HouseCityCancelHandler(BaseHandler):
    """User presses the Cancel button while choosing a city."""

    async def match(self, context: dict, db: AsyncSession) -> bool:
        return (
            context.get("user_state") == "news_house_city"
            and is_user_message_in_private(context)
            and context.get("update_type") == "message"
            and context.get("text", "").startswith(CANCEL_PREFIX)
        )

    async def handle(self, context: dict, db: AsyncSession) -> None:
        await _return_to_main_menu(
            db,
            context["user_id"],
            context["chat_id"],
            "❌ House ad creation cancelled.",
        )


# ---------------------------------------------------------------------------
# "Another City" handler
# ---------------------------------------------------------------------------
class HouseCityAnotherCityHandler(BaseHandler):
    """User wants to type a custom city name that is not in the list."""

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

        keyboard = build_cancel_back_keyboard()
        await send_message_with_keyboard(
            chat_id,
            "📍 Please type the name of your city:",
            keyboard,
        )


# ---------------------------------------------------------------------------
# "Back" handler for state "news_house_city"
# ---------------------------------------------------------------------------
class HouseCityBackHandler(BaseHandler):
    """User presses Back while choosing a city – return to main menu."""

    async def match(self, context: dict, db: AsyncSession) -> bool:
        return (
            context.get("user_state") == "news_house_city"
            and is_user_message_in_private(context)
            and context.get("update_type") == "message"
            and context.get("text") == BACK_BUTTON_TEXT
        )

    async def handle(self, context: dict, db: AsyncSession) -> None:
        await _return_to_main_menu(
            db,
            context["user_id"],
            context["chat_id"],
            "🔙 Returning to main menu.",
        )


# ---------------------------------------------------------------------------
# City input handler – handles a city name (from keyboard or typed)
# ---------------------------------------------------------------------------
class HouseCityInputHandler(BaseHandler):
    """
    Receives a city name while in 'news_house_city'.

    The text may come from the keyboard ("🇩🇪 Berlin") or be typed manually.
    We strip the flag prefix, validate, and if valid proceed (for now just
    acknowledge and return to main menu; the next phase will be implemented later).
    If invalid the user is prompted to choose again.
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

        # Try to extract city name from the button format "🇩🇪 Berlin"
        city_name = raw_text
        if raw_text.startswith(f"{CITY_FLAG} "):
            city_name = raw_text[len(CITY_FLAG) + 1 :].strip()

        if is_valid_city(city_name):
            # For now we simply acknowledge. DB insertion will be added later.
            await send_message(
                chat_id,
                f"✅ City selected: {city_name}.\n"
                "(The next step – description – will be available soon.)",
            )
            await _return_to_main_menu(
                db, user_id, chat_id, "🏠 Back to main menu."
            )
        else:
            # Invalid – keep the same keyboard and ask again
            cities = get_all_cities()
            keyboard = build_city_keyboard(cities)
            await send_message_with_keyboard(
                chat_id,
                f"❌ '{city_name}' is not in the list of available cities. "
                "Please pick one from the keyboard or use \"Another City\".",
                keyboard,
            )


# ---------------------------------------------------------------------------
# Custom city flow: Cancel handler
# ---------------------------------------------------------------------------
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
        await _return_to_main_menu(
            db,
            context["user_id"],
            context["chat_id"],
            "❌ House ad creation cancelled.",
        )


# ---------------------------------------------------------------------------
# Custom city flow: Back handler
# ---------------------------------------------------------------------------
class HouseCityCustomBackHandler(BaseHandler):
    """Go back to the city selection keyboard."""

    async def match(self, context: dict, db: AsyncSession) -> bool:
        return (
            context.get("user_state") == "news_house_city_custom"
            and is_user_message_in_private(context)
            and context.get("update_type") == "message"
            and context.get("text") == BACK_BUTTON_TEXT
        )

    async def handle(self, context: dict, db: AsyncSession) -> None:
        user_id = context["user_id"]
        chat_id = context["chat_id"]

        state_repo = BotStateRepository(db)
        state_service = BotStateService(state_repo)
        await state_service.update_user_state(user_id, "news_house_city")

        cities = get_all_cities()
        keyboard = build_city_keyboard(cities)
        await send_message_with_keyboard(
            chat_id,
            "🏠 Pick a city from the list or use \"Another City\":",
            keyboard,
        )


# ---------------------------------------------------------------------------
# Custom city input handler – accepts any free‑form text as the city name
# ---------------------------------------------------------------------------
class HouseCityCustomInputHandler(BaseHandler):
    """
    Receive the custom city name while in 'news_house_city_custom'.

    No validation is performed; we accept whatever the user types.
    """

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

        # For now just acknowledge
        await send_message(
            chat_id,
            f"✅ You entered custom city: {city_name}.\n"
            "(The next step – description – will be available soon.)",
        )
        await _return_to_main_menu(
            db, user_id, chat_id, "🏠 Back to main menu."
        )