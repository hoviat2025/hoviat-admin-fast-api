# app\modules\hilfen\handlers\stateful\auth_handlers.py
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.hilfen.core.base_handler import BaseHandler
from app.modules.hilfen.repositories.bot_state import BotStateRepository
from app.modules.hilfen.services.state_service import BotStateService
from app.modules.hilfen.services.telegram_service import send_message
from app.modules.hilfen.repositories.user_repository import HilfenUserRepository


class StartCommandHandler(BaseHandler):
    """
    Handles the `/start` command.

    Enhanced behavior with state-based registration:
    - If user exists and has first name: greet them
    - If user exists but has no first name: start registration flow
    - If user doesn't exist: create user and start registration flow
    """

    async def match(self, context: dict, db: AsyncSession) -> bool:
        text = context.get("text") or ""
        return text.startswith("/start")

    async def handle(self, context: dict, db: AsyncSession) -> None:
        chat_id = context.get("chat_id")
        user_id = context.get("user_id")

        user_repo = HilfenUserRepository(db)
        state_repo = BotStateRepository(db)
        state_service = BotStateService(state_repo)

        user = await user_repo.get_by_id(user_id)

        if user:
            # Check if user has a first name
            if not user.first_name or user.first_name.strip() == "":
                # User exists but doesn't have a first name, start registration
                await state_service.update_user_state(user_id, "waiting_for_first_name")
                await db.commit()
                await send_message(chat_id, "Welcome back! It looks like we don't have your name yet. What's your first name?")
            else:
                # User exists and has a first name
                greeting_name = user.first_name or "there"
                await send_message(chat_id, f"Hi {greeting_name}! Welcome back!")
            return

        # User doesn't exist - create minimal record
        create_data = {
            "counter": user_id,
            "user_id": user_id,
        }

        try:
            await user_repo.create(create_data)
            
            # Set state to ask for first name
            await state_service.update_user_state(user_id, "waiting_for_first_name")
            
            await db.commit()
        except Exception:
            await db.rollback()
            raise

        await send_message(chat_id, "Welcome! Let's get you registered. What's your first name?")




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
