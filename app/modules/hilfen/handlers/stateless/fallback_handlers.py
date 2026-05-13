# app\modules\hilfen\handlers\stateless\fallback_handlers.py
"""
Fallback handlers that catch unprocessed updates.

These handlers are executed LAST, after all other handlers have been checked.
They provide default responses for messages that weren't handled elsewhere.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.hilfen.core.base_handler import BaseHandler
from app.modules.hilfen.core.scenarios import is_user_message_in_private
from app.modules.hilfen.services.telegram_service import send_message


class UnhandledPrivateMessageHandler(BaseHandler):
    """
    Fallback handler for unprocessed messages in private chat.

    This handler runs AFTER all other handlers (both stateless and stateful)
    have been checked. It catches any user message in a private chat that
    wasn't handled by any other handler.
    
    IMPORTANT: This handler must be registered separately and executed
    only when no other handler has matched the update.
    """

    async def match(self, context: dict, db: AsyncSession) -> bool:
        """
        Match conditions:
        1. Message from a user (not a bot) in private chat
        2. Has text content (not just contact sharing, etc.)
        3. Is a regular message (not callback query, etc.)
        """
        return (
            is_user_message_in_private(context)
            and not context.get("is_bot", False)
            and context.get("text") is not None
            and context.get("update_type") == "message"
        )

    async def handle(self, context: dict, db: AsyncSession) -> None:
        """Send a helpful message when the bot doesn't understand."""
        chat_id = context.get("chat_id")
        await send_message(
            chat_id, 
            "متوجه نشدم. لطفاً از /start برای شروع استفاده کنید یا دوباره تلاش کنید."
        )