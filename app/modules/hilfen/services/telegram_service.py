import logging

from app.core.config import settings
from app.shared.clients.telegram import TelegramBot

logger = logging.getLogger(__name__)

# Initialize client once
telegram_bot = TelegramBot(settings.HILFEN_BOT_TOKEN)


async def send_message(chat_id: int, text: str) -> bool:
    """
    Send a message to a Telegram chat using the TelegramBot client.
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
