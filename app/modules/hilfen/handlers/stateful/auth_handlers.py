# app/modules/hilfen/handlers/stateful/auth_handlers.py
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.hilfen.core.base_handler import BaseHandler
from app.modules.hilfen.repositories.user_repository import HilfenUserRepository
from app.modules.hilfen.services.telegram_service import send_message_with_keyboard
from app.modules.hilfen.services.keyboard_service import get_main_menu_keyboard
from app.modules.hilfen.services.registration_service import ensure_registration_progress


class StartCommandHandler(BaseHandler):
    """
    Handles the /start command.

    - If the user exists and registration is complete → welcome back with main menu.
    - Otherwise, the dispatcher’s registration checkpoint already handles the
      missing fields; this handler does nothing extra.
    """

    async def match(self, context: dict, db: AsyncSession) -> bool:
        text = context.get("text") or ""
        return text.startswith("/start")

    async def handle(self, context: dict, db: AsyncSession) -> None:
        chat_id = context.get("chat_id")
        user_id = context.get("user_id")

        user_repo = HilfenUserRepository(db)
        user = await user_repo.get_by_id(user_id)

        if user is None:
            # Should not happen – dispatcher creates the user first.
            return

        # Only show the main menu if all required registration fields are present.
        required_fields_present = all([
            user.country,
            user.first_name,
            user.last_name,
            user.phone_number,
        ])

        if required_fields_present:
            greeting_name = user.first_name or "there"
            main_menu = get_main_menu_keyboard()
            await send_message_with_keyboard(
                chat_id,
                f"Hi {greeting_name}! Welcome back!",
                keyboard=main_menu,
            )
        # If registration is incomplete, do nothing – the dispatcher already
        # called ensure_registration_progress and sent the appropriate prompt.