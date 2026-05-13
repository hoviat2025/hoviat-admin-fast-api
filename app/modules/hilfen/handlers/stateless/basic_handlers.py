# app\modules\hilfen\handlers\stateless\basic_handlers.py
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


class UnhandledPrivateMessageHandler(BaseHandler):
    """
    Fallback handler for unprocessed messages in private chat.

    When no other handler matches a user's message in a private chat,
    this handler sends a "I didn't understand" message.
    
    IMPORTANT: This handler must be placed LAST in the stateless handlers list
    to ensure it only catches messages that weren't handled by others.
    """

    async def match(self, context: dict, db: AsyncSession) -> bool:
        # Only match if:
        # 1. It's a message from a user in private chat
        # 2. It's not a bot message
        # 3. There's actual text content (not just contact sharing, etc.)
        return (
            is_user_message_in_private(context)
            and not context.get("is_bot", False)
            and context.get("text") is not None
            and context.get("update_type") == "message"
        )

    async def handle(self, context: dict, db: AsyncSession) -> None:
        chat_id = context.get("chat_id")
        await send_message(
            chat_id, 
            "متوجه نشدم. لطفاً از /start برای شروع استفاده کنید یا دوباره تلاش کنید."
        )