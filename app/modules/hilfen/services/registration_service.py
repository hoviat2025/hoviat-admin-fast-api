# app/modules/hilfen/services/registration_service.py
"""
Shared registration initiation logic.

Both the /start handler and the dispatcher’s pre‑handler checkpoint use
this function to prompt the user for the next missing registration field.
It must only be called in contexts that are already verified as private
chats from a real user.
"""

import logging
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.hilfen.repositories.user_repository import HilfenUserRepository
from app.modules.hilfen.repositories.bot_state import BotStateRepository
from app.modules.hilfen.services.state_service import BotStateService
from app.modules.hilfen.services.telegram_service import send_message, request_contact

logger = logging.getLogger(__name__)

# States that indicate the user is currently answering a registration question.
_REGISTRATION_STATES = {
    "waiting_for_country",
    "waiting_for_first_name",
    "waiting_for_last_name",
    "waiting_for_phone",
}


async def ensure_registration_progress(
    db: AsyncSession,
    user_id: int,
    chat_id: int,
    username: str | None,
    telegram_first_name: str | None,
    telegram_last_name: str | None,
    user_state: str | None,
) -> bool:
    """
    Check whether the user must complete (or continue) registration.

    This function does **not** verify the chat type – the caller must already
    have confirmed that the update comes from a **private** chat with a user.

    Returns:
        True  – a registration prompt was sent **and** the DB was committed.
                The caller must NOT run any further handlers.
        False – registration is complete or no action was taken.
    """
    user_repo = HilfenUserRepository(db)
    state_repo = BotStateRepository(db)
    state_service = BotStateService(state_repo)

    # If the user is already answering a step, let the dedicated handler run.
    if user_state in _REGISTRATION_STATES:
        return False

    user = await user_repo.get_by_id(user_id)

    # ---- No database record yet ----
    if user is None:
        try:
            # Build nickname from Telegram profile data.
            nickname_parts = []
            if telegram_first_name:
                nickname_parts.append(telegram_first_name)
            if telegram_last_name:
                nickname_parts.append(telegram_last_name)
            nickname = " ".join(nickname_parts) if nickname_parts else username

            await user_repo.create_user(
                user_id=user_id,
                username=username,
                nickname=nickname,
            )
            await state_service.update_user_state(user_id, "waiting_for_country")
            await db.commit()
            await send_message(chat_id, "Welcome! Please enter your country:")
            return True
        except Exception:
            await db.rollback()
            logger.exception(
                "Failed to create user %d and start registration", user_id
            )
            await send_message(
                chat_id, "Sorry, something went wrong. Please try again."
            )
            return False  # Stop processing on failure

    # ---- User exists – fill the first missing field ----
    if not user.country:
        await state_service.update_user_state(user_id, "waiting_for_country")
        await db.commit()
        await send_message(chat_id, "Please enter your country:")
        return True

    if not user.first_name:
        await state_service.update_user_state(user_id, "waiting_for_first_name")
        await db.commit()
        await send_message(chat_id, "What's your first name?")
        return True

    if not user.last_name:
        await state_service.update_user_state(user_id, "waiting_for_last_name")
        await db.commit()
        await send_message(chat_id, "What's your last name?")
        return True

    if not user.phone_number:
        await state_service.update_user_state(user_id, "waiting_for_phone")
        await db.commit()
        await send_message(
            chat_id,
            "Please share your phone number using the button below.",
            reply_markup=request_contact(chat_id),
        )
        return True

    # All required fields are filled.
    return False