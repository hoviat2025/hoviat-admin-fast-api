# app/modules/hilfen/handlers/stateful/main_menu_handlers.py
"""
Handlers for the main‑menu reply keyboard buttons.

Each button triggers a separate handler.  They are placed **after** the
registration and /start handlers so they only fire when the user is not
in the middle of registration.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.hilfen.core.base_handler import BaseHandler
from app.modules.hilfen.repositories.bot_state import BotStateRepository
from app.modules.hilfen.services.state_service import BotStateService
from app.modules.hilfen.services.telegram_service import send_message, send_message_with_keyboard
from app.modules.hilfen.services.keyboard_service import build_city_keyboard
from app.modules.hilfen.services.city_service import get_all_cities


# ---------------------------------------------------------------------------
# House button – begins the house‑ad flow
# ---------------------------------------------------------------------------
class HouseButtonHandler(BaseHandler):
    """
    Triggered by the "🏠 House 🏠" button when the user is at the main menu.

    Sets the user state to 'news_house_city' and presents the city keyboard.
    """

    async def match(self, context: dict, db: AsyncSession) -> bool:
        return (
            context.get("update_type") == "message"
            and context.get("text") == "🏠 House 🏠"
            and context.get("user_state") is None   # only at main menu
        )

    async def handle(self, context: dict, db: AsyncSession) -> None:
        user_id = context["user_id"]
        chat_id = context["chat_id"]

        # Transition to city‑selection state
        state_repo = BotStateRepository(db)
        state_service = BotStateService(state_repo)
        await state_service.update_user_state(user_id, "news_house_city")

        cities = get_all_cities()
        keyboard = build_city_keyboard(cities)  # uses default cancel

        await send_message_with_keyboard(
            chat_id,
            "🏠 Let's create a house ad. First, pick a city:",
            keyboard,
        )


# ---------------------------------------------------------------------------
# Work and Needs button
# ---------------------------------------------------------------------------
class WorkAndNeedsButtonHandler(BaseHandler):
    async def match(self, context: dict, db: AsyncSession) -> bool:
        return (
            context.get("update_type") == "message"
            and context.get("text") == "🔖 Work and Needs 💼"
        )

    async def handle(self, context: dict, db: AsyncSession) -> None:
        await send_message(
            context["chat_id"],
            "The 'Work and Needs' section is under development."
        )


# ---------------------------------------------------------------------------
# Euro Exchange button
# ---------------------------------------------------------------------------
class EuroButtonHandler(BaseHandler):
    async def match(self, context: dict, db: AsyncSession) -> bool:
        return (
            context.get("update_type") == "message"
            and context.get("text") == "💶 Euro Exchange 💶"
        )

    async def handle(self, context: dict, db: AsyncSession) -> None:
        await send_message(
            context["chat_id"],
            "The 'Euro' section is under development."
        )


# ---------------------------------------------------------------------------
# My Profile button
# ---------------------------------------------------------------------------
class MyProfileButtonHandler(BaseHandler):
    async def match(self, context: dict, db: AsyncSession) -> bool:
        return (
            context.get("update_type") == "message"
            and context.get("text") == "👤 My Profile 👤"
        )

    async def handle(self, context: dict, db: AsyncSession) -> None:
        await send_message(
            context["chat_id"],
            "Your profile will be shown here soon."
        )


# ---------------------------------------------------------------------------
# My Ads button
# ---------------------------------------------------------------------------
class MyAdsButtonHandler(BaseHandler):
    async def match(self, context: dict, db: AsyncSession) -> bool:
        return (
            context.get("update_type") == "message"
            and context.get("text") == "📁 My Ads 📁"
        )

    async def handle(self, context: dict, db: AsyncSession) -> None:
        await send_message(
            context["chat_id"],
            "Your ads will be listed here soon."
        )


# ---------------------------------------------------------------------------
# Help and Support button
# ---------------------------------------------------------------------------
class HelpButtonHandler(BaseHandler):
    async def match(self, context: dict, db: AsyncSession) -> bool:
        return (
            context.get("update_type") == "message"
            and context.get("text") == "❔ Help and Support 📩"
        )

    async def handle(self, context: dict, db: AsyncSession) -> None:
        await send_message(
            context["chat_id"],
            "Help: You can use the menu below to navigate."
        )