from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.hilfen.core.base_handler import BaseHandler
from app.modules.hilfen.repositories.bot_state import BotStateRepository
from app.modules.hilfen.services.state_service import BotStateService
from app.modules.hilfen.services.telegram_service import send_message


class EmailInputHandler(BaseHandler):
    """
    Handles email input when the user is in the 'waiting_for_email' state.
    """

    async def match(self, context: dict, db: AsyncSession) -> bool:
        return (
            context.get("user_state") == "waiting_for_email"
            and context.get("update_type") == "message"
        )

    async def handle(self, context: dict, db: AsyncSession) -> None:
        chat_id = context.get("chat_id")
        user_id = context.get("user_id")
        email = context.get("text") or ""

        repo = BotStateRepository(db)
        state_service = BotStateService(repo)

        if "@" in email:
            await state_service.update_user_state(user_id, "waiting_for_password")

            await send_message(
                chat_id,
                "Email saved. Send password.",
            )
        else:
            await send_message(
                chat_id,
                "Invalid email. Try again.",
            )
