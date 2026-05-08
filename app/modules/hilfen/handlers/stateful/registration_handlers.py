# app/modules/hilfen/handlers/stateful/registration_handlers.py
"""
Registration handlers for collecting user information.

These handlers manage the registration flow and are responsible for
keeping the user's channel posts in sync by calling
UpdateChannelPostService after each successful data change.
"""

import logging
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio

from app.modules.hilfen.core.base_handler import BaseHandler
from app.modules.hilfen.repositories.bot_state import BotStateRepository
from app.modules.hilfen.repositories.user_repository import HilfenUserRepository
from app.modules.hilfen.services.state_service import BotStateService
from app.modules.hilfen.services.telegram_service import (
    send_message,
    send_message_with_keyboard,
    request_contact,
    remove_keyboard,
)
from app.modules.hilfen.services.keyboard_service import get_main_menu_keyboard
from app.modules.eurobot.channels.services.update_channel_post_service import (
    UpdateChannelPostService,
)

logger = logging.getLogger(__name__)


class CountryRegistrationHandler(BaseHandler):
    """
    Handles country input during registration.
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
            user_repo = HilfenUserRepository(db)
            await user_repo.update_country(user_id, country)

            state_repo = BotStateRepository(db)
            state_service = BotStateService(state_repo)
            await state_service.update_user_state(user_id, "waiting_for_first_name")

            await db.commit()
            await asyncio.sleep(5)

            # User data changed → update channel posts
            channel_service = UpdateChannelPostService(db)
            await channel_service.execute(user_id=user_id, update_source="hilfenbot")

            await send_message(
                chat_id, f"Country saved as {country}. Now, what's your first name?"
            )

        except Exception as e:
            await db.rollback()
            logger.error(f"Error saving country for user {user_id}: {e}")
            await send_message(chat_id, "Sorry, something went wrong. Please try again.")


class FirstNameRegistrationHandler(BaseHandler):
    """
    Handles first name input during registration.
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
            user_repo = HilfenUserRepository(db)
            await user_repo.update_first_name(user_id, first_name)

            state_repo = BotStateRepository(db)
            state_service = BotStateService(state_repo)
            await state_service.update_user_state(user_id, "waiting_for_last_name")

            await db.commit()

            await asyncio.sleep(5)

            # User data changed → update channel posts
            channel_service = UpdateChannelPostService(db)
            await channel_service.execute(user_id=user_id, update_source="hilfenbot")

            await send_message(
                chat_id, f"Thanks, {first_name}! Now, what's your last name?"
            )

        except Exception as e:
            await db.rollback()
            logger.error(f"Error saving first name for user {user_id}: {e}")
            await send_message(chat_id, "Sorry, something went wrong. Please try again.")


class LastNameRegistrationHandler(BaseHandler):
    """
    Handles last name input during registration.
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
            await user_repo.update_last_name(user_id, last_name)

            state_repo = BotStateRepository(db)
            state_service = BotStateService(state_repo)
            await state_service.update_user_state(user_id, "waiting_for_phone")

            await db.commit()

            # User data changed → update channel posts
            channel_service = UpdateChannelPostService(db)
            await channel_service.execute(user_id=user_id, update_source="hilfenbot")

            await request_contact(
                chat_id,
                "Great! Now please share your phone number using the button below:",
            )

        except Exception as e:
            await db.rollback()
            logger.error(f"Error saving last name for user {user_id}: {e}")
            await send_message(chat_id, "Sorry, something went wrong. Please try again.")


class PhoneRegistrationHandler(BaseHandler):
    """
    Handles phone number collection and finalises registration.
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
            await send_message(
                chat_id, "Please share your phone number using the contact sharing button."
            )
            return

        phone_number = contact.get("phone_number", "").strip()
        if not phone_number:
            await send_message(chat_id, "Invalid phone number. Please try again.")
            return

        try:
            user_repo = HilfenUserRepository(db)
            await user_repo.update_phone_number(user_id, phone_number)

            state_repo = BotStateRepository(db)
            state_service = BotStateService(state_repo)
            await state_service.update_user_state(user_id, "waiting_to_complete_register")

            await db.commit()

            # Remove the contact sharing keyboard
            await remove_keyboard(chat_id, "Phone number received. Completing registration...")

            # Update channel posts after saving phone number
            channel_service = UpdateChannelPostService(db)
            await channel_service.execute(user_id=user_id, update_source="hilfenbot")

            # Clear user state (registration complete)
            await state_service.update_user_state(user_id, None)
            await db.commit()

            user = await user_repo.get_by_id(user_id)
            greeting_name = user.first_name if user else "there"

            # Show the main menu keyboard now that registration is complete
            main_menu = get_main_menu_keyboard()
            await send_message_with_keyboard(
                chat_id,
                f"Registration complete! Welcome {greeting_name}!",
                keyboard=main_menu,
            )

        except Exception as e:
            await db.rollback()
            logger.error(f"Error saving phone number for user {user_id}: {e}")
            await send_message(chat_id, "Sorry, something went wrong. Please try again.")


class InvalidPhoneInputHandler(BaseHandler):
    """
    Handles invalid input when expecting phone contact.
    """

    async def match(self, context: dict, db: AsyncSession) -> bool:
        user_state = context.get("user_state")
        return (
            user_state == "waiting_for_phone"
            and context.get("update_type") == "message"
            and context.get("text") is not None
        )

    async def handle(self, context: dict, db: AsyncSession) -> None:
        chat_id = context.get("chat_id")
        await request_contact(
            chat_id, "Please use the contact sharing button below to share your phone number:"
        )