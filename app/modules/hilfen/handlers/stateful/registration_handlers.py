# app\modules\hilfen\handlers\stateful\registration_handlers.py
"""
Registration handlers for collecting user information.

These handlers manage the 5-step registration flow:
1. Country input (waiting_for_country)
2. First name input (waiting_for_first_name)
3. Last name input (waiting_for_last_name)
4. Phone number via contact sharing (waiting_for_phone)
5. Registration completion with update_channel_post service (waiting_to_complete_register)
"""

import logging
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.hilfen.core.base_handler import BaseHandler
from app.modules.hilfen.repositories.bot_state import BotStateRepository
from app.modules.hilfen.repositories.user_repository import HilfenUserRepository
from app.modules.hilfen.services.state_service import BotStateService
from app.modules.hilfen.services.telegram_service import (
    send_message, 
    request_contact, 
    remove_keyboard
)

logger = logging.getLogger(__name__)


class CountryRegistrationHandler(BaseHandler):
    """
    Handles country input during registration.

    Flow:
    1. User is in 'waiting_for_country' state
    2. User sends a message (country name)
    3. Handler saves country, updates state to 'waiting_for_first_name'
    4. Asks for first name
    """

    async def match(self, context: dict, db: AsyncSession) -> bool:
        user_state = context.get("user_state")
        return (
            user_state == "waiting_for_country"
            and context.get("update_type") == "message"
            and context.get("text") is not None
        )

    async def handle(self, context: dict, db: AsyncSession) -> None:
        chat_id = context.get("chat_id")
        user_id = context.get("user_id")
        country = context.get("text", "").strip()

        if not country:
            await send_message(chat_id, "Please enter your country name.")
            return

        try:
            # Update user's country
            user_repo = HilfenUserRepository(db)
            await user_repo.update_country(user_id, country)

            # Update state to ask for first name
            state_repo = BotStateRepository(db)
            state_service = BotStateService(state_repo)
            await state_service.update_user_state(user_id, "waiting_for_first_name")

            await db.commit()
            await send_message(chat_id, f"Country saved as {country}. Now, what's your first name?")
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Error saving country for user {user_id}: {e}")
            await send_message(chat_id, "Sorry, something went wrong. Please try again.")


class FirstNameRegistrationHandler(BaseHandler):
    """
    Handles first name input during registration.

    Flow:
    1. User is in 'waiting_for_first_name' state
    2. User sends a message (first name)
    3. Handler saves first name, updates state to 'waiting_for_last_name'
    4. Asks for last name
    """

    async def match(self, context: dict, db: AsyncSession) -> bool:
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
            await send_message(chat_id, "Please enter your first name.")
            return

        try:
            # Update user's first name
            user_repo = HilfenUserRepository(db)
            await user_repo.update_first_name(user_id, first_name)

            # Update state to ask for last name
            state_repo = BotStateRepository(db)
            state_service = BotStateService(state_repo)
            await state_service.update_user_state(user_id, "waiting_for_last_name")

            await db.commit()
            await send_message(chat_id, f"Thanks, {first_name}! Now, what's your last name?")
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Error saving first name for user {user_id}: {e}")
            await send_message(chat_id, "Sorry, something went wrong. Please try again.")


class LastNameRegistrationHandler(BaseHandler):
    """
    Handles last name input during registration.

    Flow:
    1. User is in 'waiting_for_last_name' state
    2. User sends a message (last name)
    3. Handler saves last name, updates nickname (first + last), updates state to 'waiting_for_phone'
    4. Requests phone number via contact sharing
    """

    async def match(self, context: dict, db: AsyncSession) -> bool:
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
            await send_message(chat_id, "Please enter your last name.")
            return

        try:
            user_repo = HilfenUserRepository(db)
            
            # Update user's last name
            await user_repo.update_last_name(user_id, last_name)
            
            # # Get user to update nickname
            # user = await user_repo.get_by_id(user_id)
            # if user:
            #     # Update nickname: first_name + " " + last_name
            #     nickname = f"{user.first_name or ''} {last_name}".strip()
            #     await user_repo.update_nickname(user_id, nickname)

            # Update state to ask for phone number
            state_repo = BotStateRepository(db)
            state_service = BotStateService(state_repo)
            await state_service.update_user_state(user_id, "waiting_for_phone")

            await db.commit()
            
            # Request phone number via contact sharing
            await request_contact(chat_id, "Great! Now please share your phone number using the button below:")
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Error saving last name for user {user_id}: {e}")
            await send_message(chat_id, "Sorry, something went wrong. Please try again.")


class PhoneRegistrationHandler(BaseHandler):
    """
    Handles phone number collection via contact sharing.

    Flow:
    1. User is in 'waiting_for_phone' state
    2. User shares contact (must be contact, not text)
    3. Handler saves phone number, updates state to 'waiting_to_complete_register'
    4. Calls update_channel_post service via proxy
    5. When service completes, clears state and notifies user
    """

    async def match(self, context: dict, db: AsyncSession) -> bool:
        user_state = context.get("user_state")
        return (
            user_state == "waiting_for_phone"
            and context.get("update_type") == "message"
            and context.get("contact") is not None
        )

    async def handle(self, context: dict, db: AsyncSession) -> None:
        chat_id = context.get("chat_id")
        user_id = context.get("user_id")
        contact = context.get("contact")
        
        if not contact or "phone_number" not in contact:
            await send_message(chat_id, "Please share your phone number using the contact sharing button.")
            return

        phone_number = contact.get("phone_number", "").strip()
        if not phone_number:
            await send_message(chat_id, "Invalid phone number. Please try again.")
            return

        try:
            # Update user's phone number
            user_repo = HilfenUserRepository(db)
            await user_repo.update_phone_number(user_id, phone_number)

            # Update state to indicate registration is being completed
            state_repo = BotStateRepository(db)
            state_service = BotStateService(state_repo)
            await state_service.update_user_state(user_id, "waiting_to_complete_register")

            await db.commit()
            
            # Remove the contact sharing keyboard
            await remove_keyboard(chat_id, "Phone number received. Completing registration...")
            
            # Call update_channel_post service via proxy
            try:
                from app.modules.hilfen.services.update_channel_post_service import UpdateChannelPostService
                update_service = UpdateChannelPostService(db)
                await update_service.execute(user_id)
                logger.info(f"Successfully updated channel post for user {user_id}")
            except Exception as e:
                logger.error(f"Failed to call update_channel_post for user {user_id}: {e}")
                # Continue with registration even if service fails
                # The user is already registered in our database
            
            # Clear user state (registration complete)
            await state_service.update_user_state(user_id, None)
            await db.commit()
            
            # Get user for personalized message
            user = await user_repo.get_by_id(user_id)
            greeting_name = user.first_name if user else "there"
            
            await send_message(chat_id, f"Registration complete! Welcome {greeting_name}!")
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Error saving phone number for user {user_id}: {e}")
            await send_message(chat_id, "Sorry, something went wrong. Please try again.")


class InvalidPhoneInputHandler(BaseHandler):
    """
    Handles invalid input when expecting phone contact.

    When user is in 'waiting_for_phone' state but sends text instead of contact,
    remind them to use the contact sharing button.
    """

    async def match(self, context: dict, db: AsyncSession) -> bool:
        user_state = context.get("user_state")
        return (
            user_state == "waiting_for_phone"
            and context.get("update_type") == "message"
            and context.get("text") is not None  # User sent text instead of contact
        )

    async def handle(self, context: dict, db: AsyncSession) -> None:
        chat_id = context.get("chat_id")
        await request_contact(chat_id, "Please use the contact sharing button below to share your phone number:")
