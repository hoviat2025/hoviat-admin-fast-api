from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.hilfen.core.base_handler import BaseHandler
from app.modules.hilfen.core.scenarios import is_user_message_in_private
from app.modules.hilfen.services.telegram_service import send_message


class IgnoreBotMessagesHandler(BaseHandler):
    """
    Prevent the bot from responding to other bots.
    """

    async def match(self, context: dict, db: AsyncSession) -> bool:
        return context.get("is_bot", False)

    async def handle(self, context: dict, db: AsyncSession) -> None:
        return


class SamCommandHandler(BaseHandler):
    """
    Simple test command that only works in private chats.

    Demonstrates how to use scenario checkers inside `match`.
    """

    async def match(self, context: dict, db: AsyncSession) -> bool:
        # Only answer /sam when the user is talking to the bot privately
        if not is_user_message_in_private(context):
            return False

        text = context.get("text") or ""
        return text.strip().startswith("/sam")

    async def handle(self, context: dict, db: AsyncSession) -> None:
        chat_id = context.get("chat_id")
        await send_message(chat_id, "sung")
