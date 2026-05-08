import json
import logging
import asyncio

from app.core.database import AsyncSessionLocal
from app.modules.hilfen.core.context_extractor import extract_context
from app.modules.hilfen.core.scenarios import (
    is_user_message_in_private,
    is_album_update,
)
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
from app.modules.hilfen.services.album_cache_service import AlbumCacheService
from app.modules.eurobot.channels.services.update_channel_post_service import UpdateChannelPostService

debug_logger = logging.getLogger("telegram.update.debug")
logger = logging.getLogger(__name__)

# Single album cache instance (shared across all updates in this process)
album_cache = AlbumCacheService()
# Track media groups that are already being collected (to avoid duplicate timers)
_active_album_groups: set[str] = set()


def _build_telegram_nickname(first_name: str | None, last_name: str | None) -> str | None:
    """Combine Telegram first/last name into the nickname stored in DB."""
    parts = [p for p in (first_name, last_name) if p]
    return " ".join(parts).strip() if parts else None


async def _collect_album_and_possibly_stop(update: dict, context: dict) -> bool:
    """
    Album gathering logic.

    If the current update belongs to an album (and is NOT already a composite):
      1. Store it in the cache.
      2. If this is the first part for this group, schedule a background task
         that waits 5 seconds, assembles all parts, and re‑dispatches a
         composite update.
      3. Return **True** so the dispatcher stops processing this individual part.

    Returns:
        True  – caller must return immediately (the update is an album part).
        False – this is not an album update; proceed normally.
    """
    if not is_album_update(context):
        return False

    media_group_id = context["media_group_id"]
    album_cache.add_part(media_group_id, update)

    if media_group_id not in _active_album_groups:
        _active_album_groups.add(media_group_id)
        asyncio.create_task(_process_album_after_delay(media_group_id))

    # Always stop processing the individual part.
    return True


async def _process_album_after_delay(media_group_id: str):
    """
    Wait 5 seconds, collect all cached parts, assemble a composite update,
    and dispatch it through the normal pipeline.
    """
    try:
        await asyncio.sleep(5)

        parts = album_cache.collect(media_group_id)
        if not parts:
            logger.warning("Album %s timed out with no parts – ignoring.", media_group_id)
            return

        # Use the first part as the template for user/chat info.
        # The first part might be a 'message' or an 'edited_message'.
        first_part = parts[0]
        first_msg = first_part.get("message") or first_part.get("edited_message", {})
        if not first_msg:
            logger.error(
                "Album %s first part has neither 'message' nor 'edited_message' – ignoring.",
                media_group_id,
            )
            return

        # Collect photo arrays from all parts (order is preserved as received).
        album_photos = []
        for part in parts:
            msg = part.get("message") or part.get("edited_message", {})
            photo = msg.get("photo")
            if photo:
                album_photos.append(photo)

        if not album_photos:
            logger.error("Album %s collected no photos – ignoring.", media_group_id)
            return

        # Build a composite update that looks like a normal 'message' but carries
        # an extra 'album_photos' field and a flag indicating it's composite.
        composite = {
            "update_id": first_part.get("update_id"),
            "message": {
                **first_msg,
                "photo": album_photos[0],          # first photo array (compatibility)
                "album_photos": album_photos,       # all photo arrays
                "media_group_id": media_group_id,   # keep for reference (won't loop)
                "is_album_composite": True,         # prevent re-collection
            }
        }

        # Dispatch the composite update through the whole pipeline.
        await process_telegram_update(composite)

    except Exception:
        logger.exception("Unexpected error while processing album %s", media_group_id)
    finally:
        # Always clean up the active set so future albums with the same ID work.
        _active_album_groups.discard(media_group_id)


async def process_telegram_update(update: dict) -> None:
    """
    Main Telegram update dispatcher – scenario‑driven.

    Pipeline:
        1. Print incoming update (debug).
        2. Extract normalized context.
        3. Execute stateless handlers (NO DB).
        4. **Album collection** – if the update is part of an album, store it,
           schedule assembly, and stop processing this individual part.
        5. **Private‑chat scenario** ...
        6. **Non‑private with known user** ...
        7. Fallback handlers.
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

    # --- 4) ALBUM COLLECTION (BEFORE ANY DB STEPS) ---
    if await _collect_album_and_possibly_stop(update, context):
        # This is an album part – the composite will be dispatched later.
        return

    # =======================================================================
    # SCENARIO 1 : Private chat between bot and user
    # =======================================================================
    if is_user_message_in_private(context):
        async with AsyncSessionLocal() as db:
            try:
                # 4a) Load user state
                state_repo = BotStateRepository(db)
                state_service = BotStateService(state_repo)
                context["user_state"] = await state_service.fetch_user_state(
                    context["user_id"]
                )

                user_repo = HilfenUserRepository(db)
                user = await user_repo.get_by_id(context["user_id"])
                user_data_changed = True  # keep as True for now

                # 4b) Ensure user record exists + sync Telegram fields
                if user is None:
                    nickname = _build_telegram_nickname(
                        context.get("first_name"), context.get("last_name")
                    ) or context.get("username")
                    await user_repo.create_user(
                        user_id=context["user_id"],
                        username=context.get("username"),
                        nickname=nickname,
                    )
                    user_data_changed = True
                    user = await user_repo.get_by_id(context["user_id"])
                    logger.info(f"Minimal user created for id {context['user_id']}")
                else:
                    new_username = context.get("username")
                    if new_username and user.username != new_username:
                        user.username = new_username
                        user_data_changed = True
                    new_nick = _build_telegram_nickname(
                        context.get("first_name"), context.get("last_name")
                    )
                    if new_nick and user.nickname != new_nick:
                        user.nickname = new_nick
                        user_data_changed = True

                # 4c) Update channel posts if basic data changed
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

                # 4e) Registration checkpoint
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
                    return

                # 4f) Stateful handlers
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

    # =======================================================================
    # SCENARIO 2 : Non‑private chat with a known user
    # =======================================================================
    elif context.get("user_id"):
        async with AsyncSessionLocal() as db:
            try:
                state_repo = BotStateRepository(db)
                state_service = BotStateService(state_repo)
                context["user_state"] = await state_service.fetch_user_state(
                    context["user_id"]
                )
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

    # --- 5) FALLBACK HANDLERS (NO DB SESSION) ---
    for handler in FALLBACK_HANDLERS:
        if await handler.match(context, None):
            await handler.handle(context, None)
            return

    # --- 6) NO HANDLER MATCHED ---
    debug_logger.debug(
        f"No handler matched update type: {context['update_type']}"
    )