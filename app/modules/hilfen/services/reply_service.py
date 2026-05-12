# app/modules/hilfen/services/reply_service.py
"""
Service for building Telegram reply_parameters objects used for cross‑chat
external replies (Bot API 6.0+).

Each method returns a dict suitable for passing as the `reply_parameters`
argument to sendMessage / sendPhoto / sendMediaGroup / etc.
"""

import logging
from typing import Optional

from app.core.config import settings
from app.modules.hilfen.repositories.user_repository import HilfenUserRepository
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class ReplyService:
    """
    Generates reply_parameters dicts for quoting a specific message in another chat.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def build_admin_channel_reply(self, user_id: int) -> Optional[dict]:
        """Quote the user's post in ADMIN_CHANNEL_ID."""
        user_repo = HilfenUserRepository(self.db)
        user = await user_repo.get_by_id(user_id)
        if not user or not user.admin_message_id:
            logger.warning(
                "Cannot build admin channel reply: user %s has no admin_message_id",
                user_id,
            )
            return None

        try:
            target_message_id = int(user.admin_message_id)
        except (ValueError, TypeError):
            logger.error(
                "Invalid admin_message_id %r for user %s",
                user.admin_message_id,
                user_id,
            )
            return None

        try:
            target_chat_id = str(settings.ADMIN_CHANNEL_ID)
        except AttributeError:
            logger.error("ADMIN_CHANNEL_ID is not set")
            return None

        return {
            "message_id": target_message_id,
            "chat_id": target_chat_id,
        }

    async def build_hilfen_channel_reply(self, user_id: int) -> Optional[dict]:
        """Quote the user's post in HILFEN_CHANNEL_ID."""
        user_repo = HilfenUserRepository(self.db)
        user = await user_repo.get_by_id(user_id)
        if not user or not user.hilfen_message_id:
            logger.warning(
                "Cannot build hilfen channel reply: user %s has no hilfen_message_id",
                user_id,
            )
            return None

        try:
            target_message_id = int(user.hilfen_message_id)
        except (ValueError, TypeError):
            logger.error(
                "Invalid hilfen_message_id %r for user %s",
                user.hilfen_message_id,
                user_id,
            )
            return None

        try:
            target_chat_id = str(settings.HILFEN_CHANNEL_ID)
        except AttributeError:
            logger.error("HILFEN_CHANNEL_ID is not set")
            return None

        return {
            "message_id": target_message_id,
            "chat_id": target_chat_id,
        }