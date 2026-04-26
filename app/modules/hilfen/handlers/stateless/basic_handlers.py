from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.hilfen.core.base_handler import BaseHandler
from app.modules.hilfen.services.telegram_service import send_message


class IgnoreBotMessagesHandler(BaseHandler):
    """
    Prevent the bot from responding to other bots.
    """

    async def match(self, context: dict, db: AsyncSession) -> bool:
        return context.get("is_bot", False)

    async def handle(self, context: dict, db: AsyncSession) -> None:
        return


class StartCommandHandler(BaseHandler):
    """
    Handles the /start command.
    """

    async def match(self, context: dict, db: AsyncSession) -> bool:
        text = context.get("text") or ""
        return text.startswith("/start")

    async def handle(self, context: dict, db: AsyncSession) -> None:
        chat_id = context.get("chat_id")

        await send_message(chat_id, "Welcome to Hilfen!")


class SamCommandHandler(BaseHandler):
    """
    Simple test command handler.

    Responds to the `/sam` command with the message "sung".
    This handler is stateless and exists mainly to validate the
    dispatcher → handler → service flow during early development.
    """

    async def match(self, context: dict, db: AsyncSession) -> bool:
        text = context.get("text") or ""
        return text.strip().startswith("/sam")

    async def handle(self, context: dict, db: AsyncSession) -> None:
        chat_id = context.get("chat_id")

        await send_message(chat_id, "sung")
