# app/modules/hilfen/handlers/stateful/house_news_admin_handlers.py
"""
Handlers for admin actions on house news in the check‑admin channel.

- Decline callback (inline button)
- Collection of the decline reason
"""

import logging
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.modules.hilfen.core.base_handler import BaseHandler
from app.modules.hilfen.constants import ADMIN_DECLINE_PREFIX
from app.modules.hilfen.repositories.bot_state import BotStateRepository
from app.modules.hilfen.repositories.news_repository import NewsRepository
from app.modules.hilfen.repositories.user_repository import HilfenUserRepository
from app.modules.hilfen.services.state_service import BotStateService
from app.modules.hilfen.services.telegram_service import (
    send_message,
    send_message_with_reply,
    edit_message_text,
    edit_message_reply_markup,
)
from app.modules.hilfen.services.admin_service import AdminService
from app.modules.hilfen.services.news_format_service import format_decline_comment

logger = logging.getLogger(__name__)

ADMIN_DECLINE_STATE_PREFIX = "admin_news_house_decline+"


class AdminDeclineCallbackHandler(BaseHandler):
    """
    Catches the 'Decline' inline button click in the check‑admin channel.
    Sets the admin's state so the next reply is treated as the decline reason.
    """

    async def match(self, context: dict, db: AsyncSession) -> bool:
        if context.get("update_type") != "callback_query":
            return False
        # Only in the check‑admin channel
        if str(context.get("chat_id")) != settings.CHECK_ADMIN_CHANNEL_ID:
            return False
        data = context.get("text", "")
        if not data.startswith(ADMIN_DECLINE_PREFIX):
            return False
        # Sender must be an admin
        # return AdminService.is_admin(context.get("user_id"))
        return True

    async def handle(self, context: dict, db: AsyncSession) -> None:
        user_id = context["user_id"]
        chat_id = context["chat_id"]          # check‑admin channel
        data = context["text"]

        try:
            news_id = int(data[len(ADMIN_DECLINE_PREFIX):])
        except ValueError:
            logger.warning(f"Invalid decline callback data: {data}")
            return

        # Set admin's state
        state_repo = BotStateRepository(db)
        state_service = BotStateService(state_repo)
        new_state = f"{ADMIN_DECLINE_STATE_PREFIX}{news_id}"
        await state_service.update_user_state(user_id, new_state)

        # Load news to get the handler message id
        news_repo = NewsRepository(db)
        news = await news_repo.get_by_id(news_id)
        if not news or not news.admin_handler_message_id:
            logger.error(f"News {news_id} or its handler message not found")
            return

        # Edit the handler message: remove buttons, ask for decline reason
        await edit_message_text(
            chat_id,
            news.admin_handler_message_id,
            "❌ This ad was declined.\nPlease reply to this message with the reason for the decline."
        )
        await edit_message_reply_markup(
            chat_id,
            news.admin_handler_message_id,
            reply_markup={"inline_keyboard": []}
        )


class AdminDeclineMessageHandler(BaseHandler):
    """
    Catches the admin's reply with the decline reason in the check‑admin channel.
    Finalises the decline: updates DB, notifies the user, posts a comment.
    """

    async def match(self, context: dict, db: AsyncSession) -> bool:
        if context.get("update_type") != "message":
            return False
        # Must be in the check‑admin channel
        if str(context.get("chat_id")) != settings.CHECK_ADMIN_CHANNEL_ID:
            return False
        # # Only for admins
        # if not AdminService.is_admin(context.get("user_id")):
        #     return False
        state = context.get("user_state")
        if not isinstance(state, str) or not state.startswith(ADMIN_DECLINE_STATE_PREFIX):
            return False
        # Must be a reply to the correct handler message
        reply_to = context.get("reply_to_message_id")
        if reply_to is None:
            return False

        try:
            news_id = int(state[len(ADMIN_DECLINE_STATE_PREFIX):])
        except ValueError:
            return False

        news_repo = NewsRepository(db)
        news = await news_repo.get_by_id(news_id)
        if not news or news.admin_handler_message_id != reply_to:
            return False
        return True

    async def handle(self, context: dict, db: AsyncSession) -> None:
        admin_id = context["user_id"]
        check_admin_channel = context["chat_id"]
        decline_text = context["text"]
        state = context["user_state"]
        news_id = int(state[len(ADMIN_DECLINE_STATE_PREFIX):])

        # 1) Update news row
        news_repo = NewsRepository(db)
        news = await news_repo.get_by_id(news_id)
        if not news:
            logger.error(f"News {news_id} vanished during decline handling")
            return

        await news_repo.update_news(
            news_id=news_id,
            status="declined",
            decline_message=decline_text,
        )

        # 2) Notify the original user
        if news.user_id and news.preview_message_id:
            await send_message_with_reply(
                news.user_id,
                f"❌ Your house ad was declined.\nReason: {decline_text}",
                news.preview_message_id,
            )

        # 3) Edit the admin handler message (remove buttons, show reason)
        if news.admin_handler_message_id:
            await edit_message_text(
                check_admin_channel,
                news.admin_handler_message_id,
                f"❌ House ad declined.\nReason: {decline_text}",
            )
            await edit_message_reply_markup(
                check_admin_channel,
                news.admin_handler_message_id,
                reply_markup={"inline_keyboard": []},
            )

        # 4) Post a decline comment in the admin group
        user_repo = HilfenUserRepository(db)
        user = await user_repo.get_by_id(news.user_id)
        if user and user.admin_group_message_id:
            comment_text = format_decline_comment(news, decline_text)
            try:
                admin_group_id = int(settings.ADMIN_GROUP_ID)
            except (ValueError, TypeError):
                logger.error("ADMIN_GROUP_ID is not a valid integer")
            else:
                await send_message_with_reply(
                    admin_group_id,
                    comment_text,
                    int(user.admin_group_message_id),
                )

        # 5) Clear the admin's state
        state_repo = BotStateRepository(db)
        state_service = BotStateService(state_repo)
        await state_service.update_user_state(admin_id, None)