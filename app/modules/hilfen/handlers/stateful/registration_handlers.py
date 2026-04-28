# app\modules\hilfen\handlers\stateful\registration_handlers.py
"""
Registration handlers for collecting user information.

These handlers manage the registration flow using state-based interactions.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.hilfen.core.base_handler import BaseHandler
from app.modules.hilfen.repositories.bot_state import BotStateRepository
from app.modules.hilfen.repositories.user_repository import HilfenUserRepository
from app.modules.hilfen.services.state_service import BotStateService
from app.modules.hilfen.services.telegram_service import send_message


class FirstNameRegistrationHandler(BaseHandler):
    """
    Handles the first name registration flow.

    Flow:
    1. User is in 'waiting_for_first_name' state
    2. User sends a message (their first name)
    3. Handler saves the first name, clears the state, and asks for last name
    """

    async def match(self, context: dict, db: AsyncSession) -> bool:
        # Check if user is in the 'waiting_for_first_name' state
        user_state = context.get("user_state")
        return (
            user_state == "waiting_for_first_name"
            and context.get("update_type") == "message"
            and context.get("text") is not None
        )

    async def handle(self, context: dict, db: AsyncSession) -> None:
        chat_id = context.get("chat_id")
        user_id = context.get("user_id")
        first_name = context.get("text", "").strip()

        if not first_name:
            await send_message(chat_id, "Please send your first name.")
            return

        # Update user's first name
        user_repo = HilfenUserRepository(db)
        await user_repo.update_first_name(user_id, first_name)

        # Update user's state to ask for last name
        state_repo = BotStateRepository(db)
        state_service = BotStateService(state_repo)
        await state_service.update_user_state(user_id, "waiting_for_last_name")

        await db.commit()
        await send_message(chat_id, f"Thanks, {first_name}! Now, what's your last name?")


class LastNameRegistrationHandler(BaseHandler):
    """
    Handles the last name registration flow.

    Flow:
    1. User is in 'waiting_for_last_name' state
    2. User sends a message (their last name)
    3. Handler saves the last name and completes registration
    """

    async def match(self, context: dict, db: AsyncSession) -> bool:
        # Check if user is in the 'waiting_for_last_name' state
        user_state = context.get("user_state")
        return (
            user_state == "waiting_for_last_name"
            and context.get("update_type") == "message"
            and context.get("text") is not None
        )

    async def handle(self, context: dict, db: AsyncSession) -> None:
        chat_id = context.get("chat_id")
        user_id = context.get("user_id")
        last_name = context.get("text", "").strip()

        if not last_name:
            await send_message(chat_id, "Please send your last name.")
            return

        # Update user's last name
        user_repo = HilfenUserRepository(db)
        await user_repo.update_field(user_id, "last_name", last_name)

        # Clear the user's state (registration complete)
        state_repo = BotStateRepository(db)
        state_service = BotStateService(state_repo)
        await state_service.update_user_state(user_id, None)

        await db.commit()
        
        # Get user's first name for personalized message
        user = await user_repo.get_by_id(user_id)
        first_name = user.first_name if user else "there"
        
        await send_message(chat_id, f"Registration complete! Welcome {first_name} {last_name}!")


class StartWithRegistrationHandler(BaseHandler):
    """
    Enhanced start handler that initiates registration if user doesn't have a first name.

    This handler replaces or complements the existing StartCommandHandler.
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
                await send_message(chat_id, "Welcome! It looks like we don't have your name yet. What's your first name?")
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
