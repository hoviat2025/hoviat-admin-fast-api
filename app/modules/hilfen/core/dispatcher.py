import json
import logging

from app.core.database import AsyncSessionLocal
from app.modules.hilfen.core.context_extractor import extract_context
from app.modules.hilfen.core.scenarios import is_user_message_in_private
from app.modules.hilfen.handlers.registry import (
    STATELESS_HANDLERS,
    STATEFUL_HANDLERS,
    FALLBACK_HANDLERS,
)
from app.modules.hilfen.repositories.bot_state import BotStateRepository
from app.modules.hilfen.repositories.user_repository import HilfenUserRepository
from app.modules.hilfen.services.state_service import BotStateService
from app.modules.hilfen.services.registration_service import ensure_registration_progress
from app.modules.hilfen.services.ban_service import BanService
from app.modules.hilfen.services.telegram_service import send_message
from app.modules.eurobot.channels.services.update_channel_post_service import UpdateChannelPostService

debug_logger = logging.getLogger("telegram.update.debug")
logger = logging.getLogger(__name__)


def _build_telegram_nickname(first_name: str | None, last_name: str | None) -> str | None:
    """Combine Telegram first/last name into the nickname stored in DB."""
    parts = [p for p in (first_name, last_name) if p]
    return " ".join(parts).strip() if parts else None


async def process_telegram_update(update: dict) -> None:
    """
    Main Telegram update dispatcher – scenario‑driven.

    Pipeline:
        1. Print incoming update (debug).
        2. Extract normalized context.
        3. Execute stateless handlers (NO DB).
        4. **Private‑chat scenario**:
              a) Ensure user record exists, sync Telegram nickname/username.
              b) If any basic field changed → update channel posts.
              c) Check ban → stop if banned.
              d) Registration checkpoint (prompt missing fields).
              e) Execute stateful handlers (which update channel themselves).
        5. **Non‑private but with a known user** (e.g. groups):
              Load user state → execute stateful handlers.
        6. Fallback handlers.
        7. Otherwise ignore the update.
    """

    # --- 1) PRINT RAW TELEGRAM UPDATE ---
    try:
        pretty_json = json.dumps(update, indent=2, ensure_ascii=False)
        debug_logger.info("Incoming Telegram update:\n%s", pretty_json)
    except Exception:
        debug_logger.warning("Failed to pretty-print Telegram update.")

    # --- 2) EXTRACT CONTEXT ---
    context = extract_context(update)
    if context["update_type"] == "unknown":
        return

    # --- 3) STATELESS HANDLERS (NO DB SESSION) ---
    for handler in STATELESS_HANDLERS:
        if await handler.match(context, None):
            await handler.handle(context, None)
            return

    # =======================================================================
    # SCENARIO 1 : Private chat between bot and user
    # =======================================================================
    if is_user_message_in_private(context):
        async with AsyncSessionLocal() as db:
            try:
                # 4a) Load user state (used later by registration & stateful handlers)
                state_repo = BotStateRepository(db)
                state_service = BotStateService(state_repo)
                context["user_state"] = await state_service.fetch_user_state(
                    context["user_id"]
                )

                user_repo = HilfenUserRepository(db)
                user = await user_repo.get_by_id(context["user_id"])
                user_data_changed = True #usually set to false but for now we want this to be true as defualt

                # 4b) Ensure user record exists + sync Telegram fields
                if user is None:
                    # Create minimal user from Telegram data
                    nickname = _build_telegram_nickname(
                        context.get("first_name"), context.get("last_name")
                    ) or context.get("username")
                    await user_repo.create_user(
                        user_id=context["user_id"],
                        username=context.get("username"),
                        nickname=nickname,
                    )
                    user_data_changed = True
                    # Re‑fetch so we have the ORM object for later steps
                    user = await user_repo.get_by_id(context["user_id"])
                    logger.info(f"Minimal user created for id {context['user_id']}")
                else:
                    # Sync username
                    new_username = context.get("username")
                    if new_username and user.username != new_username:
                        user.username = new_username
                        user_data_changed = True

                    # Sync Telegram nickname (derived from first + last name)
                    new_nick = _build_telegram_nickname(
                        context.get("first_name"), context.get("last_name")
                    )
                    if new_nick and user.nickname != new_nick:
                        user.nickname = new_nick
                        user_data_changed = True

                # 4c) Update channel posts **only if** basic user data changed
                if user_data_changed:
                    channel_service = UpdateChannelPostService(db)
                    await channel_service.execute(
                        user_id=context["user_id"], update_source="hilfenbot"
                    )

                # 4d) Ban check
                ban_service = BanService(db)
                if await ban_service.is_banned(user):
                    await send_message(context["chat_id"], "You are banned.")
                    return

                # 4e) Registration checkpoint (any update type in private)
                registration_handled = await ensure_registration_progress(
                    db=db,
                    user_id=context["user_id"],
                    chat_id=context["chat_id"],
                    username=context.get("username"),
                    telegram_first_name=context.get("first_name"),
                    telegram_last_name=context.get("last_name"),
                    user_state=context["user_state"],
                )
                if registration_handled:
                    # A registration prompt was sent – stop further processing.
                    # No channel update here because no user fields were changed.
                    return

                # 4f) Stateful handlers (they handle their own channel updates)
                for handler in STATEFUL_HANDLERS:
                    if await handler.match(context, db):
                        await handler.handle(context, db)
                        await db.commit()
                        return

                # No stateful handler matched – commit any pending sync
                await db.commit()

            except Exception as e:
                await db.rollback()
                logger.error(
                    f"Error processing update for user {context['user_id']}: {e}",
                    exc_info=True,
                )
                # Continue to fallback handlers

    # =======================================================================
    # SCENARIO 2 : Non‑private chat with a known user (e.g. group)
    # =======================================================================
    elif context.get("user_id"):
        async with AsyncSessionLocal() as db:
            try:
                # Load user state (needed by stateful handlers)
                state_repo = BotStateRepository(db)
                state_service = BotStateService(state_repo)
                context["user_state"] = await state_service.fetch_user_state(
                    context["user_id"]
                )

                # Only stateful handlers – no private‑only operations
                for handler in STATEFUL_HANDLERS:
                    if await handler.match(context, db):
                        await handler.handle(context, db)
                        await db.commit()
                        return

                await db.commit()

            except Exception as e:
                await db.rollback()
                logger.error(
                    f"Error processing update for user {context['user_id']}: {e}",
                    exc_info=True,
                )
                # Continue to fallback handlers

    # --- 5) FALLBACK HANDLERS (NO DB SESSION) ---
    for handler in FALLBACK_HANDLERS:
        if await handler.match(context, None):
            await handler.handle(context, None)
            return

    # --- 6) NO HANDLER MATCHED ---
    debug_logger.debug(
        f"No handler matched update type: {context['update_type']}"
    )