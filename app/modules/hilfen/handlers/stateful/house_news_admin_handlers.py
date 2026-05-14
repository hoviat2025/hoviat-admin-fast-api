# app/modules/hilfen/handlers/stateful/house_news_admin_handlers.py
"""
Handlers for admin actions on house news in the check‑admin channel.

- Decline callback (inline button)
- Collection of the decline reason
- Confirm callback → publish to news channel
"""

import asyncio
import json
import logging
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.modules.hilfen.core.base_handler import BaseHandler
from app.modules.hilfen.constants import ADMIN_DECLINE_PREFIX, ADMIN_CONFIRM_PREFIX
from app.modules.hilfen.repositories.bot_state import BotStateRepository
from app.modules.hilfen.repositories.news_repository import NewsRepository
from app.modules.hilfen.repositories.user_repository import HilfenUserRepository
from app.modules.hilfen.services.state_service import BotStateService
from app.modules.hilfen.services.telegram_service import (
    send_message,
    send_message_with_reply,
    edit_message_text,
    edit_message_reply_markup,
    send_photo,
    send_media_group,
    send_message_return_id,
    send_contact_mention,
)
from app.modules.hilfen.services.news_format_service import (
    format_decline_comment,
    format_published_comment,
)
from app.modules.hilfen.services.reply_service import ReplyService
from app.modules.hilfen.services.channel_mapping_service import get_house_channel
from app.modules.hilfen.services.comment_cache_service import comment_mapping_cache
from app.modules.hilfen.services.keyboard_service import (
    build_admin_published_keyboard,
    build_user_published_keyboard,
)

logger = logging.getLogger(__name__)

ADMIN_DECLINE_STATE_PREFIX = "admin_news_house_decline+"


# ---------------------------------------------------------------------------
# Helper: wait for comment mapping to appear in cache
# ---------------------------------------------------------------------------
async def _wait_for_comment_mapping(
    channel_id: int, original_msg_id: int, timeout: float = 45.0
) -> tuple[int, int] | None:
    """
    Poll the comment cache every 2 seconds for up to ```timeout``` seconds.
    Returns (group_chat_id, group_message_id) or None on timeout.
    """
    await asyncio.sleep(10)

    logger.info(
        "Waiting for comment mapping: channel=%s, original_msg=%s (timeout=%ss)",
        channel_id,
        original_msg_id,
        timeout,
    )
    # deadline = asyncio.get_event_loop().time() + timeout
    # while True:
    for i in range(4):
        mapping = comment_mapping_cache.get_mapping(channel_id, original_msg_id)
        if mapping is not None:
            logger.info("Comment mapping found: %s", mapping)
            return mapping
        # if asyncio.get_event_loop().time() >= deadline:
            logger.warning(
                "Timeout waiting for comment mapping (channel %s, msg %s)",
                channel_id,
                original_msg_id,
            )
            return None
        await asyncio.sleep(10)


# ---------------------------------------------------------------------------
# Decline handlers
# ---------------------------------------------------------------------------
class AdminDeclineCallbackHandler(BaseHandler):
    """Catches the 'Decline' inline button click in the check‑admin channel."""

    async def match(self, context: dict, db: AsyncSession) -> bool:
        if context.get("update_type") != "callback_query":
            return False
        if str(context.get("chat_id")) != settings.CHECK_ADMIN_CHANNEL_ID:
            return False
        data = context.get("text", "")
        if not data.startswith(ADMIN_DECLINE_PREFIX):
            return False
        return True

    async def handle(self, context: dict, db: AsyncSession) -> None:
        user_id = context["user_id"]
        chat_id = context["chat_id"]
        data = context["text"]

        try:
            news_id = int(data[len(ADMIN_DECLINE_PREFIX):])
        except ValueError:
            logger.warning(f"Invalid decline callback data: {data}")
            return

        state_repo = BotStateRepository(db)
        state_service = BotStateService(state_repo)
        new_state = f"{ADMIN_DECLINE_STATE_PREFIX}{news_id}"
        await state_service.update_user_state(user_id, new_state)

        news_repo = NewsRepository(db)
        news = await news_repo.get_by_id(news_id)
        if not news or not news.admin_handler_message_id:
            logger.error(f"News {news_id} or its handler message not found")
            return

        await edit_message_text(
            chat_id,
            news.admin_handler_message_id,
            "❌ این آگهی رد شد.\nلطفاً دلیل رد را در پاسخ به این پیام بنویسید.",
        )
        await edit_message_reply_markup(
            chat_id,
            news.admin_handler_message_id,
            reply_markup={"inline_keyboard": []},
        )


class AdminDeclineMessageHandler(BaseHandler):
    """Catches the admin's reply with the decline reason in the check‑admin channel."""

    async def match(self, context: dict, db: AsyncSession) -> bool:
        if context.get("update_type") != "channel_post":
            return False
        if str(context.get("chat_id")) != settings.CHECK_ADMIN_CHANNEL_ID:
            return False
        state = context.get("user_state")
        if not isinstance(state, str) or not state.startswith(ADMIN_DECLINE_STATE_PREFIX):
            return False
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

        if news.user_id and news.preview_message_id:
            await send_message_with_reply(
                news.user_id,
                f"❌ آگهی خانه شما رد شد.\nدلیل: {decline_text}",
                news.preview_message_id,
            )

        if news.admin_handler_message_id:
            await edit_message_text(
                check_admin_channel,
                news.admin_handler_message_id,
                f"❌ آگهی خانه رد شد.\nدلیل: {decline_text}",
            )
            await edit_message_reply_markup(
                check_admin_channel,
                news.admin_handler_message_id,
                reply_markup={"inline_keyboard": []},
            )

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

        state_repo = BotStateRepository(db)
        state_service = BotStateService(state_repo)
        await state_service.update_user_state(admin_id, None)


# ---------------------------------------------------------------------------
# Confirm handler (Phase 3)
# ---------------------------------------------------------------------------
class AdminConfirmCallbackHandler(BaseHandler):
    """Admin clicked 'Confirm' in check‑admin channel – publish the house ad."""

    async def match(self, context: dict, db: AsyncSession) -> bool:
        if context.get("update_type") != "callback_query":
            return False
        if str(context.get("chat_id")) != settings.CHECK_ADMIN_CHANNEL_ID:
            return False
        data = context.get("text", "")
        return data.startswith(ADMIN_CONFIRM_PREFIX)

    async def handle(self, context: dict, db: AsyncSession) -> None:
        admin_id = context["user_id"]
        check_admin_channel = int(settings.CHECK_ADMIN_CHANNEL_ID)
        data = context["text"]
        try:
            news_id = int(data[len(ADMIN_CONFIRM_PREFIX):])
        except ValueError:
            logger.warning(f"Invalid confirm callback data: {data}")
            return

        news_repo = NewsRepository(db)
        news = await news_repo.get_by_id(news_id)
        if not news:
            logger.error(f"News {news_id} not found for confirm")
            return

        # ---- 0) Capture admin-edited preview text ----
        edited_text = context.get("callback_query_reply_text")
        if edited_text and edited_text.strip():
            if news.news_text != edited_text:
                logger.info(
                    "Updating news_text for news %s to admin-edited version",
                    news_id,
                )
                await news_repo.update_news(news_id=news_id, news_text=edited_text)
                news = await news_repo.get_by_id(news_id)
                if not news:
                    logger.error("News %s disappeared after update", news_id)
                    return

        # ---- 1) Target channel ----
        target_channel = get_house_channel(news.city)
        if not target_channel:
            logger.error(f"No target channel for city '{news.city}'")
            await send_message(check_admin_channel, "⚠️ هیچ کانالی برای این شهر پیکربندی نشده است.")
            return

        logger.info("Target channel for city '%s': %s", news.city, target_channel)

        # ---- 2) Cross‑chat reply on the user's Hilfen channel post ----
        reply_service = ReplyService(db)
        hilfen_reply_params = await reply_service.build_hilfen_channel_reply(news.user_id)

        # ---- 3) Send preview to target channel ----
        preview_text = news.news_text or ""
        media_objects = None
        if news.media:
            try:
                media_objects = json.loads(news.media)
            except Exception:
                logger.warning(f"Invalid media JSON for news {news.id}")

        main_message_id = None
        if media_objects and len(media_objects) > 0:
            if len(media_objects) == 1:
                result = await send_photo(
                    target_channel,
                    media_objects[0]["file_id"],
                    caption=preview_text,
                    reply_parameters=hilfen_reply_params,
                )
                if result:
                    main_message_id = result["message_id"]
            else:
                media_list = [
                    {"type": "photo", "media": obj["file_id"]} for obj in media_objects
                ]
                results = await send_media_group(
                    target_channel,
                    media_list,
                    caption=preview_text,
                    reply_parameters=hilfen_reply_params,
                )
                if results:
                    main_message_id = results[0]["message_id"]
        else:
            main_message_id = await send_message_return_id(
                target_channel,
                preview_text,
                reply_parameters=hilfen_reply_params,
            )

        if main_message_id is None:
            logger.error("Failed to send news to target channel")
            await send_message(check_admin_channel, "⚠️ انتشار ناموفق بود. لطفاً دوباره تلاش کنید.")
            return

        logger.info(
            "Published to channel %s, message_id=%s. Waiting for comment mapping...",
            target_channel,
            main_message_id,
        )

        await news_repo.update_news(
            news_id=news_id,
            main_channel_id=target_channel,
            main_channel_message_id=main_message_id,
            status="publishing",
        )

        # ---- 4) Wait for auto‑forwarded comment ----
        mapping = await _wait_for_comment_mapping(target_channel, main_message_id)
        group_chat_id = None
        group_msg_id = None
        if mapping:
            group_chat_id, group_msg_id = mapping
        else:
            logger.warning("No comment mapping appeared; continuing without contact comment")

        # ---- 5) Send contact comment with text mention ----
        contact_msg_id = None
        if group_chat_id and group_msg_id:
            if news.user_id:
                contact_msg_id = await send_contact_mention(
                    group_chat_id,
                    news.user_id,
                    reply_parameters={"message_id": group_msg_id},
                )
                if contact_msg_id:
                    await news_repo.update_news(
                        news_id=news_id,
                        contact_group_message_id=contact_msg_id,
                        group_chat_id=group_chat_id,
                        group_message_id=group_msg_id,
                    )

        # ---- 6) Post published comments in admin / hilfen / main groups ----
        comment_text = format_published_comment(news)
        user_repo = HilfenUserRepository(db)
        user = await user_repo.get_by_id(news.user_id)
        if user:
            # Admin group
            if user.admin_group_message_id:
                try:
                    admin_group_id = int(settings.ADMIN_GROUP_ID)
                    await send_message_with_reply(
                        admin_group_id,
                        comment_text,
                        int(user.admin_group_message_id),
                    )
                except Exception as e:
                    logger.error("Failed to post in admin group: %s", e)
            # Hilfen group
            if user.hilfen_group_message_id:
                try:
                    hilfen_group_id = int(settings.HILFEN_GROUP_ID)
                    await send_message_with_reply(
                        hilfen_group_id,
                        comment_text,
                        int(user.hilfen_group_message_id),
                    )
                except Exception as e:
                    logger.error("Failed to post in hilfen group: %s", e)
            # Main group (group_message_id)
            if user.group_message_id:
                try:
                    main_group_id = int(settings.MAIN_GROUP_ID)
                    await send_message_with_reply(
                        main_group_id,
                        comment_text,
                        int(user.group_message_id),
                    )
                except Exception as e:
                    logger.error("Failed to post in main group: %s", e)

        # ---- 7) Build post URL ----
        channel_id_str = str(target_channel).removeprefix("-100")
        post_url = f"https://t.me/c/{channel_id_str}/{main_message_id}"

        # ---- 8) Edit admin handler message ----
        if news.admin_handler_message_id:
            await edit_message_text(
                check_admin_channel,
                news.admin_handler_message_id,
                "✅ آگهی با موفقیت منتشر شد.",
            )
            await edit_message_reply_markup(
                check_admin_channel,
                news.admin_handler_message_id,
                reply_markup={
                    "inline_keyboard": build_admin_published_keyboard(post_url)
                },
            )

        # ---- 9) Edit user handler message ----
        if news.user_handle_message_id and news.user_id:
            await edit_message_text(
                news.user_id,
                news.user_handle_message_id,
                "✅ آگهی خانه شما منتشر شد!",
            )
            await edit_message_reply_markup(
                news.user_id,
                news.user_handle_message_id,
                reply_markup={
                    "inline_keyboard": build_user_published_keyboard(news_id, post_url)
                },
            )

        # ---- 10) Mark as published ----
        await news_repo.update_news(news_id=news_id, status="published")