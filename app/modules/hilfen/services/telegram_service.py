# app/modules/hilfen/services/telegram_service.py
import logging
from typing import Optional

from app.core.config import settings
from app.shared.clients.telegram import TelegramBot

logger = logging.getLogger(__name__)

# Initialize client once
telegram_bot = TelegramBot(settings.HILFEN_BOT_TOKEN)


async def send_message(chat_id: int, text: str) -> bool:
    """
    Send a plain text message (no keyboard).
    Returns True on success, False on failure.
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
    Returns True on success, False on failure.
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
    Returns True on success, False on failure.
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
    Returns True on success, False on failure.
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






async def send_message_with_inline_keyboard(
    chat_id: int,
    text: str,
    inline_keyboard: list[list[dict]],
    reply_to_message_id: int | None = None,
) -> Optional[int]:
    """
    Send a text message with an inline keyboard, optionally replying to a message.
    Returns the message_id of the sent message on success, None on failure.
    """
    payload = {
        "chat_id": chat_id,
        "text": text,
        "reply_markup": {"inline_keyboard": inline_keyboard},
    }
    if reply_to_message_id is not None:
        payload["reply_to_message_id"] = reply_to_message_id

    response = await telegram_bot.send_request("sendMessage", payload)
    if not response.success:
        logger.error(
            "Telegram sendMessage (inline) failed",
            extra={
                "chat_id": chat_id,
                "error": response.error_message,
                "status_code": response.status_code,
            },
        )
        return None

    result = response.data.get("result", {})
    return result.get("message_id")


async def edit_message_text(
    chat_id: int,
    message_id: int,
    text: str,
) -> bool:
    """
    Edit the text of a message sent by the bot.
    Returns True on success, False on failure.
    """
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
    }

    response = await telegram_bot.send_request("editMessageText", payload)
    if not response.success:
        logger.error(
            "Telegram editMessageText failed",
            extra={
                "chat_id": chat_id,
                "message_id": message_id,
                "error": response.error_message,
                "status_code": response.status_code,
            },
        )
        return False

    return True


async def edit_message_reply_markup(
    chat_id: int,
    message_id: int,
    reply_markup: dict | None = None,
) -> bool:
    """
    Edit only the inline keyboard of a message (e.g., remove it).
    Returns True on success, False on failure.
    """
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup

    response = await telegram_bot.send_request("editMessageReplyMarkup", payload)
    if not response.success:
        logger.error(
            "Telegram editMessageReplyMarkup failed",
            extra={
                "chat_id": chat_id,
                "message_id": message_id,
                "error": response.error_message,
                "status_code": response.status_code,
            },
        )
        return False

    return True


async def send_message_with_reply(
    chat_id: int,
    text: str,
    reply_to_message_id: int,
) -> bool:
    """
    Send a plain text message replying to a specific message.
    Returns True on success, False on failure.
    """
    payload = {
        "chat_id": chat_id,
        "text": text,
        "reply_to_message_id": reply_to_message_id,
    }
    response = await telegram_bot.send_request("sendMessage", payload)
    if not response.success:
        logger.error(
            "Telegram sendMessage with reply failed",
            extra={
                "chat_id": chat_id,
                "reply_to": reply_to_message_id,
                "error": response.error_message,
                "status_code": response.status_code,
            },
        )
        return False
    return True


async def send_message_return_id(
    chat_id: int,
    text: str,
    reply_parameters: dict | None = None,  
    parse_mode: str | None = None, 
) -> Optional[int]:
    """
    Send a plain text message and return the message_id.
    Returns None on failure.
    """
    payload = {
        "chat_id": chat_id,
        "text": text,
    }
    if reply_parameters is not None:         
        payload["reply_parameters"] = reply_parameters

    if parse_mode is not None:              
        payload["parse_mode"] = parse_mode

    response = await telegram_bot.send_request("sendMessage", payload)
    if not response.success:
        logger.error(
            "Telegram sendMessage (return id) failed",
            extra={
                "chat_id": chat_id,
                "text": text,
                "error": response.error_message,
                "status_code": response.status_code,
            },
        )
        return None
    result = response.data.get("result", {})
    return result.get("message_id")


async def send_photo(
    chat_id: int,
    photo: str,          # file_id
    caption: str = "",
    reply_parameters: dict | None = None,    # <-- NEW
) -> Optional[dict]:
    """
    Send a single photo with an optional caption.
    Returns the full message object on success, None on failure.
    """
    payload = {
        "chat_id": chat_id,
        "photo": photo,
        "caption": caption,
    }
    if reply_parameters is not None:          # <-- NEW
        payload["reply_parameters"] = reply_parameters

    response = await telegram_bot.send_request("sendPhoto", payload)
    if not response.success:
        logger.error(
            "Telegram sendPhoto failed",
            extra={
                "chat_id": chat_id,
                "error": response.error_message,
                "status_code": response.status_code,
            },
        )
        return None

    return response.data.get("result")


async def send_media_group(
    chat_id: int,
    media: list[dict],
    caption: str = "",
    reply_parameters: dict | None = None,    # <-- NEW
) -> Optional[list[dict]]:
    """
    Send a media group (album).
    `media` is a list of objects like {"type": "photo", "media": file_id}.
    Only the first element carries the caption.
    Returns a list of message objects on success, None on failure.
    """
    if not media:
        return None

    media_payload = []
    for idx, item in enumerate(media):
        entry = {
            "type": "photo",
            "media": item["media"],
        }
        if idx == 0 and caption:
            entry["caption"] = caption
        media_payload.append(entry)

    payload = {
        "chat_id": chat_id,
        "media": media_payload,
    }
    if reply_parameters is not None:          # <-- NEW
        payload["reply_parameters"] = reply_parameters

    response = await telegram_bot.send_request("sendMediaGroup", payload)
    if not response.success:
        logger.error(
            "Telegram sendMediaGroup failed",
            extra={
                "chat_id": chat_id,
                "error": response.error_message,
                "status_code": response.status_code,
            },
        )
        return None

    return response.data.get("result")