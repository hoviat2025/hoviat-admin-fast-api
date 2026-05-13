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
    Triggered by the "🏠 خانه 🏠" button when the user is at the main menu.

    Sets the user state to 'news_house_city' and presents the city keyboard.
    """

    async def match(self, context: dict, db: AsyncSession) -> bool:
        return (
            context.get("update_type") == "message"
            and context.get("text") == "🏠 خانه 🏠"
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
            "🏠 بیایید یک آگهی خانه ایجاد کنیم. ابتدا یک شهر انتخاب کنید:",
            keyboard,
        )


# ---------------------------------------------------------------------------
# Work and Needs button
# ---------------------------------------------------------------------------
class WorkAndNeedsButtonHandler(BaseHandler):
    async def match(self, context: dict, db: AsyncSession) -> bool:
        return (
            context.get("update_type") == "message"
            and context.get("text") == "🔖 کار و نیازمندی‌ها 💼"
        )

    async def handle(self, context: dict, db: AsyncSession) -> None:
        await send_message(
            context["chat_id"],
            "بخش «کار و نیازمندی‌ها» در حال توسعه است."
        )


# ---------------------------------------------------------------------------
# Euro Exchange button
# ---------------------------------------------------------------------------
class EuroButtonHandler(BaseHandler):
    async def match(self, context: dict, db: AsyncSession) -> bool:
        return (
            context.get("update_type") == "message"
            and context.get("text") == "💶 تبادل یورو 💶"
        )

    async def handle(self, context: dict, db: AsyncSession) -> None:
        await send_message(
            context["chat_id"],
            "بخش «تبادل یورو» در حال توسعه است."
        )


# ---------------------------------------------------------------------------
# My Profile button
# ---------------------------------------------------------------------------
class MyProfileButtonHandler(BaseHandler):
    async def match(self, context: dict, db: AsyncSession) -> bool:
        return (
            context.get("update_type") == "message"
            and context.get("text") == "👤 پروفایل من 👤"
        )

    async def handle(self, context: dict, db: AsyncSession) -> None:
        await send_message(
            context["chat_id"],
            "پروفایل شما به زودی اینجا نمایش داده می‌شود."
        )


# ---------------------------------------------------------------------------
# My Ads button
# ---------------------------------------------------------------------------
class MyAdsButtonHandler(BaseHandler):
    async def match(self, context: dict, db: AsyncSession) -> bool:
        return (
            context.get("update_type") == "message"
            and context.get("text") == "📁 آگهی‌های من 📁"
        )

    async def handle(self, context: dict, db: AsyncSession) -> None:
        await send_message(
            context["chat_id"],
            "آگهی‌های شما به زودی اینجا فهرست می‌شوند."
        )


# ---------------------------------------------------------------------------
# Help and Support button
# ---------------------------------------------------------------------------
class HelpButtonHandler(BaseHandler):
    async def match(self, context: dict, db: AsyncSession) -> bool:
        return (
            context.get("update_type") == "message"
            and context.get("text") == "❔ راهنما و پشتیبانی 📩"
        )

    async def handle(self, context: dict, db: AsyncSession) -> None:
        await send_message(
            context["chat_id"],
            "راهنما: می‌توانید از منوی زیر برای پیمایش استفاده کنید."
        )