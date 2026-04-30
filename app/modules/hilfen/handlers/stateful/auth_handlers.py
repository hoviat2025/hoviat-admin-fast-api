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

    Registration flow:
    1. Check if user exists in database (users_eurobot table)
    2. If user exists: do nothing (registration already complete)
    3. If user doesn't exist: 
       - Create user with username and nickname from Telegram profile
       - Set state to 'waiting_for_country'
       - Ask for country
    """

    async def match(self, context: dict, db: AsyncSession) -> bool:
        text = context.get("text") or ""
        return text.startswith("/start")

    async def handle(self, context: dict, db: AsyncSession) -> None:
        chat_id = context.get("chat_id")
        user_id = context.get("user_id")
        username = context.get("username")
        first_name = context.get("first_name")
        last_name = context.get("last_name")

        user_repo = HilfenUserRepository(db)
        state_repo = BotStateRepository(db)
        state_service = BotStateService(state_repo)

        # Check if user exists in database
        user = await user_repo.get_by_id(user_id)

        if user:
            # User exists - registration already complete
            # Optionally send a welcome message
            greeting_name = user.first_name or "there"
            await send_message(chat_id, f"Hi {greeting_name}! Welcome back!")
            return

        # User doesn't exist - start registration
        try:
            # Create user with Telegram profile data
            await user_repo.create_user(
                user_id=user_id,
                username=username,
                first_name=first_name,
                last_name=last_name
            )
            
            # Set state to ask for country
            await state_service.update_user_state(user_id, "waiting_for_country")
            
            await db.commit()
            
            # Ask for country
            await send_message(chat_id, "Welcome! Please enter your country:")
            
        except Exception as e:
            await db.rollback()
            # Log error and send generic message to user
            await send_message(chat_id, "Sorry, something went wrong. Please try again.")
            raise
