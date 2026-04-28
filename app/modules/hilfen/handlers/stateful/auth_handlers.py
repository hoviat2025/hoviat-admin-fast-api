from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.hilfen.core.base_handler import BaseHandler
from app.modules.hilfen.repositories.bot_state import BotStateRepository
from app.modules.hilfen.services.state_service import BotStateService
from app.modules.hilfen.services.telegram_service import send_message
from app.modules.hilfen.repositories.user_repository import HilfenUserRepository


class StartCommandHandler(BaseHandler):
    """
    Handles the `/start` command.

    Behavior:
    - Checks whether the Telegram user already exists in the database.
    - If the user exists, greets them using their stored first name if available.
    - If the user does not exist, creates a minimal user record and commits it.

    Transaction ownership stays at the handler layer so repository methods remain
    focused on data access and match the broader project style.
    """

    async def match(self, context: dict, db: AsyncSession) -> bool:
        text = context.get("text") or ""
        return text.startswith("/start")

    async def handle(self, context: dict, db: AsyncSession) -> None:
        chat_id = context.get("chat_id")
        user_id = context.get("user_id")

        repo = HilfenUserRepository(db)

        user = await repo.get_by_id(user_id)

        if user:
            greeting_name = user.first_name or "there"
            await send_message(chat_id, f"Hi {greeting_name}!")
            return

        create_data = {
            "counter": user_id,
            "user_id": user_id,
        }

        try:
            await repo.create(create_data)
            await db.commit()
        except Exception:
            await db.rollback()
            raise

        await send_message(chat_id, "Hello stranger!")


class EmailInputHandler(BaseHandler):
    """
    Handles email input when the user is in the `waiting_for_email` state.

    The handler performs minimal validation, updates the user state, and commits
    the state transition when the input is acceptable.
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
            try:
                await state_service.update_user_state(user_id, "waiting_for_password")
                await db.commit()
            except Exception:
                await db.rollback()
                raise

            await send_message(chat_id, "Email saved. Send password.")
        else:
            await send_message(chat_id, "Invalid email. Try again.")
