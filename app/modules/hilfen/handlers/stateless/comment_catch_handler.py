# app/modules/hilfen/handlers/stateless/comment_catch_handler.py
"""
Stateless handler that captures automatically forwarded comments from a channel
into its discussion group and stores the mapping in CommentMappingCache.

Comments originating from the HILFEN or ADMIN channels are intentionally skipped
here; they are handled by a dedicated DB‑backed service in the dispatcher.
"""

import logging
from app.core.config import settings
from app.modules.hilfen.core.base_handler import BaseHandler
from app.modules.hilfen.core.scenarios import is_auto_forwarded_comment
from app.modules.hilfen.services.comment_cache_service import comment_mapping_cache

logger = logging.getLogger(__name__)


class CommentCatchHandler(BaseHandler):
    """
    Match: update is an automatic forward of a channel post to its group,
           *unless* the pair is one of the special (HILFEN / ADMIN) channels.
    Action: record (channel_id, original_message_id) → (group_chat_id, group_message_id).
    """

    async def match(self, context: dict, db=None) -> bool:
        if not (
            context.get("update_type") == "message"
            and is_auto_forwarded_comment(context)
        ):
            return False

        channel_id = context["sender_chat_id"]
        group_chat_id = context["chat_id"]

        # Convert settings IDs to int for safe comparison (Telegram IDs are ints).
        try:
            hilfen_channel_id = int(settings.HILFEN_CHANNEL_ID)
            hilfen_group_id = int(settings.HILFEN_GROUP_ID)
            admin_channel_id = int(settings.ADMIN_CHANNEL_ID)
            admin_group_id = int(settings.ADMIN_GROUP_ID)
        except (ValueError, TypeError):
            logger.error("Invalid channel/group ID in config – cannot convert to int.")
            return False  # better to skip than to incorrectly match

        logger.debug(
            "Checking special channels: channel_id=%s (%s), group_chat_id=%s (%s) "
            "against Hilfen(%d/%d) Admin(%d/%d)",
            channel_id, type(channel_id).__name__,
            group_chat_id, type(group_chat_id).__name__,
            hilfen_channel_id, hilfen_group_id,
            admin_channel_id, admin_group_id,
        )

        if (channel_id == hilfen_channel_id and group_chat_id == hilfen_group_id) or \
           (channel_id == admin_channel_id and group_chat_id == admin_group_id):
            logger.debug("Skipping special-channel comment in CommentCatchHandler.")
            return False

        logger.debug(
            "CommentCatchHandler matched for general comment from channel %s to group %s.",
            channel_id,
            group_chat_id,
        )
        return True

    async def handle(self, context: dict, db=None) -> None:
        channel_id = context["sender_chat_id"]
        original_msg_id = context["forward_origin_message_id"]
        group_chat_id = context["chat_id"]
        group_msg_id = context["message_id"]

        if None in (channel_id, original_msg_id, group_chat_id, group_msg_id):
            logger.warning("Incomplete comment forward data; skipping.")
            return

        comment_mapping_cache.add_mapping(
            channel_id, original_msg_id, group_chat_id, group_msg_id
        )
        logger.info(
            "Comment mapping stored: channel %s orig %s -> group %s msg %s",
            channel_id,
            original_msg_id,
            group_chat_id,
            group_msg_id,
        )