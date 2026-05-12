# app/modules/hilfen/handlers/stateless/comment_catch_handler.py
"""
Stateless handler that captures automatically forwarded comments from a channel
into its discussion group and stores the mapping in CommentMappingCache.
"""

import logging
from app.modules.hilfen.core.base_handler import BaseHandler
from app.modules.hilfen.core.scenarios import is_auto_forwarded_comment
from app.modules.hilfen.services.comment_cache_service import comment_mapping_cache

logger = logging.getLogger(__name__)


class CommentCatchHandler(BaseHandler):
    """
    Match: update is an automatic forward of a channel post to its group.
    Action: record (channel_id, original_message_id) → (group_chat_id, group_message_id).
    """

    async def match(self, context: dict, db=None) -> bool:
        return (
            context.get("update_type") == "message"
            and is_auto_forwarded_comment(context)
        )

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