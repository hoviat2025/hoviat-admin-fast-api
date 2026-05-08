# app/modules/hilfen/services/telegram_service.py
import logging

from app.core.config import settings
from app.shared.clients.telegram import TelegramBot

logger = logging.getLogger(__name__)

# Initialize client once
telegram_bot = TelegramBot(settings.HILFEN_BOT_TOKEN)


async def send_message(chat_id: int, text: str) -> bool:
    """
    Send a plain text message (no keyboard).
    """
    payload = {
        "chat_id": chat_id,
        "text": text,
    }

    response = await telegram_bot.send_request("sendMessage", payload)

    if not response.success:
        logger.error(
            "Telegram sendMessage failed",
            extra={
                "chat_id": chat_id,
                "text": text,
                "error": response.error_message,
                "status_code": response.status_code,
            },
        )
        return False

    return True


async def send_message_with_keyboard(
    chat_id: int,
    text: str,
    keyboard: list[list[dict]],
) -> bool:
    """
    Send a message with a custom reply keyboard attached.
    """
    payload = {
        "chat_id": chat_id,
        "text": text,
        "reply_markup": {
            "keyboard": keyboard,
            "resize_keyboard": True,
        },
    }

    response = await telegram_bot.send_request("sendMessage", payload)

    if not response.success:
        logger.error(
            "Telegram sendMessage with keyboard failed",
            extra={
                "chat_id": chat_id,
                "text": text,
                "error": response.error_message,
                "status_code": response.status_code,
            },
        )
        return False

    return True


async def request_contact(
    chat_id: int, text: str = "Please share your phone number:"
) -> bool:
    """
    Send a message with a contact request button.
    """
    payload = {
        "chat_id": chat_id,
        "text": text,
        "reply_markup": {
            "keyboard": [[{
                "text": "📱 Share Phone Number",
                "request_contact": True,
            }]],
            "resize_keyboard": True,
            "one_time_keyboard": True,
        },
    }

    response = await telegram_bot.send_request("sendMessage", payload)

    if not response.success:
        logger.error(
            "Telegram contact request failed",
            extra={
                "chat_id": chat_id,
                "text": text,
                "error": response.error_message,
                "status_code": response.status_code,
            },
        )
        return False

    return True


async def remove_keyboard(chat_id: int, text: str) -> bool:
    """
    Send a message and remove any existing keyboard.
    """
    payload = {
        "chat_id": chat_id,
        "text": text,
        "reply_markup": {
            "remove_keyboard": True,
        },
    }

    response = await telegram_bot.send_request("sendMessage", payload)

    if not response.success:
        logger.error(
            "Telegram remove keyboard failed",
            extra={
                "chat_id": chat_id,
                "text": text,
                "error": response.error_message,
                "status_code": response.status_code,
            },
        )
        return False

    return True