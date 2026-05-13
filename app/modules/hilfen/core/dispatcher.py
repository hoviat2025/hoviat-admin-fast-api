import json
import logging
import asyncio

from app.core.exceptions import ServiceError
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.modules.hilfen.core.context_extractor import extract_context
from app.modules.hilfen.core.scenarios import (
    is_user_message_in_private,
    is_album_update,
    is_auto_forwarded_comment,
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
from app.modules.eurobot.channels.services.set_admin_message_service import SetAdminMessageService
from app.modules.eurobot.channels.services.set_hilfen_message_service import SetHilfenMessageService
from app.modules.eurobot.channels.schemas.set_admin_message_request import (
    SetAdminMessageRequest,
    OriginalUpdate as AdminOriginalUpdate,
    Message as AdminMessage,
    ForwardOrigin as AdminForwardOrigin,
    ExternalReply as AdminExternalReply,
)
from app.modules.eurobot.channels.schemas.set_hilfen_message_request import (
    SetHilfenMessageRequest,
    OriginalUpdate as HilfenOriginalUpdate,
    Message as HilfenMessage,
    ForwardOrigin as HilfenForwardOrigin,
    ExternalReply as HilfenExternalReply,
)

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
    ...
    """
    if not is_album_update(context):
        return False

    media_group_id = context["media_group_id"]
    album_cache.add_part(media_group_id, update)

    if media_group_id not in _active_album_groups:
        _active_album_groups.add(media_group_id)
        asyncio.create_task(_process_album_after_delay(media_group_id))

    return True


async def _process_album_after_delay(media_group_id: str):
    """
    Wait, collect all cached parts, assemble a composite update, and dispatch.
    """
    try:
        await asyncio.sleep(15)
        parts = album_cache.collect(media_group_id)
        if not parts:
            logger.warning("Album %s timed out with no parts – ignoring.", media_group_id)
            return

        try:
            def _get_message_id(part: dict) -> int:
                msg = part.get("message") or part.get("edited_message", {})
                return int(msg.get("message_id", 0))
            parts.sort(key=_get_message_id)
        except Exception:
            logger.warning("Could not sort album parts by message_id; using original order")

        first_part = parts[0]
        first_msg = first_part.get("message") or first_part.get("edited_message", {})
        if not first_msg:
            logger.error("Album %s first part has neither 'message' nor 'edited_message' – ignoring.", media_group_id)
            return

        album_photos = []
        for part in parts:
            msg = part.get("message") or part.get("edited_message", {})
            photo = msg.get("photo")
            if photo:
                album_photos.append(photo)

        if not album_photos:
            logger.error("Album %s collected no photos – ignoring.", media_group_id)
            return

        composite = {
            "update_id": first_part.get("update_id"),
            "message": {
                **first_msg,
                "photo": album_photos[0],
                "album_photos": album_photos,
                "media_group_id": media_group_id,
                "is_album_composite": True,
            }
        }
        await process_telegram_update(composite)
    except Exception:
        logger.exception("Unexpected error while processing album %s", media_group_id)
    finally:
        _active_album_groups.discard(media_group_id)


async def _handle_special_channel_comment(update: dict, context: dict) -> bool:
    """
    If the update is an auto‑forwarded comment from one of the two special
    channel/group pairs (HILFEN or ADMIN), open a DB session and call the
    corresponding service to store the mapping.

    Returns True if the update was handled (and further processing should stop).
    """
    if not (
        context.get("update_type") == "message"
        and is_auto_forwarded_comment(context)
    ):
        return False

    channel_id = context["sender_chat_id"]
    group_chat_id = context["chat_id"]

    # Convert config IDs to int for safe comparison (Telegram IDs are ints).
    try:
        hilfen_channel_id = int(settings.HILFEN_CHANNEL_ID)
        hilfen_group_id = int(settings.HILFEN_GROUP_ID)
        admin_channel_id = int(settings.ADMIN_CHANNEL_ID)
        admin_group_id = int(settings.ADMIN_GROUP_ID)
    except (ValueError, TypeError):
        logger.error("Invalid channel/group ID in config – cannot convert to int.")
        return False

    if channel_id == hilfen_channel_id and group_chat_id == hilfen_group_id:
        service_kind = "hilfen"
    elif channel_id == admin_channel_id and group_chat_id == admin_group_id:
        service_kind = "admin"
    else:
        return False

    logger.info("Handling special-channel comment for %s", service_kind)

    # In an auto‑forwarded channel→group message there is no `external_reply`.
    # The original channel post ID is `forward_origin_message_id`.  We use it
    # both as the lookup key and as the “admin/hilfen message ID” because
    # they refer to the same channel post.
    original_post_id = context["forward_origin_message_id"]
    group_msg_id = context["message_id"]
    external_reply_message_id =context["external_reply_message_id"]
    if None in (original_post_id, group_msg_id,external_reply_message_id):
        logger.warning("Missing IDs for %s comment; skipping.", service_kind)
        return True   # still stop processing, nothing we can do

    try:
        async with AsyncSessionLocal() as db:
            if service_kind == "hilfen":
                service = SetHilfenMessageService(db)
                request = SetHilfenMessageRequest(
                    original_update=HilfenOriginalUpdate(
                        message=HilfenMessage(
                            message_id=group_msg_id,                     # group message ID
                            forward_origin=HilfenForwardOrigin(
                                message_id=original_post_id              # channel post ID
                            ),
                            external_reply=HilfenExternalReply(
                                message_id=int(external_reply_message_id)               # external_reply_message_id 
                            ),
                        )
                    )
                )                
                # service = SetHilfenMessageService(db)
                # request = SetHilfenMessageRequest(
                #     original_update=update
                # )
            else:  # admin
                service = SetAdminMessageService(db)
                request = SetAdminMessageRequest(
                    original_update=AdminOriginalUpdate(
                        message=AdminMessage(
                            message_id=group_msg_id,
                            forward_origin=AdminForwardOrigin(
                                message_id=original_post_id
                            ),
                            external_reply=AdminExternalReply(
                                message_id=external_reply_message_id
                            ),
                        )
                    )
                )

            logger.debug(
                "Calling %s service with group_msg_id=%s, original_post_id=%s",
                service_kind, group_msg_id, original_post_id,
            )
            await service.execute(request)
            await db.commit()
            logger.info("Successfully stored %s comment mapping.", service_kind)

    except ServiceError as e:
        # Expected: staging row updated but not yet complete.
        logger.info(
            "Staging incomplete for %s comment (normal): %s", service_kind, e
        )
    except Exception:
        logger.exception("Failed to process %s comment.", service_kind)
    # Always stop further processing for these updates.
    return True


async def process_telegram_update(update: dict) -> None:
    """
    Main Telegram update dispatcher – scenario‑driven.
    ...
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

    # --- 3) ALBUM COLLECTION ---
    if await _collect_album_and_possibly_stop(update, context):
        return

    # --- 4) STATELESS HANDLERS (NO DB SESSION) ---
    for handler in STATELESS_HANDLERS:
        if await handler.match(context, None):
            await handler.handle(context, None)
            return

    # --- 5) SPECIAL‑CHANNEL COMMENT (HILFEN / ADMIN, WITH DB) ---
    if await _handle_special_channel_comment(update, context):
        return

    # =======================================================================
    # SCENARIO 1 : Private chat between bot and user
    # =======================================================================
    if is_user_message_in_private(context):
        async with AsyncSessionLocal() as db:
            try:
                state_repo = BotStateRepository(db)
                state_service = BotStateService(state_repo)
                context["user_state"] = await state_service.fetch_user_state(
                    context["user_id"]
                )

                user_repo = HilfenUserRepository(db)
                user = await user_repo.get_by_id(context["user_id"])
                user_data_changed = True

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

                if user_data_changed:
                    channel_service = UpdateChannelPostService(db)
                    await channel_service.execute(
                        user_id=context["user_id"], update_source="hilfenbot"
                    )

                ban_service = BanService(db)
                if await ban_service.is_banned(user):
                    await send_message(context["chat_id"], "شما مسدود شده‌اید.")
                    return

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

    # --- 6) FALLBACK HANDLERS (NO DB SESSION) ---
    for handler in FALLBACK_HANDLERS:
        if await handler.match(context, None):
            await handler.handle(context, None)
            return

    # --- 7) NO HANDLER MATCHED ---
    debug_logger.debug(
        f"No handler matched update type: {context['update_type']}"
    )