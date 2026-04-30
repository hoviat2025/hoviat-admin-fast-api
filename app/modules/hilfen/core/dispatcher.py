# app/modules/hilfen/core/dispatcher.py
import json
import logging
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.modules.hilfen.core.context_extractor import extract_context
from app.modules.hilfen.core.scenarios import is_user_message_in_private
from app.modules.hilfen.handlers.registry import (
    STATELESS_HANDLERS,
    STATEFUL_HANDLERS,
    FALLBACK_HANDLERS,
)
from app.modules.hilfen.repositories.bot_state import BotStateRepository
from app.modules.hilfen.services.state_service import BotStateService
from app.modules.hilfen.services.registration_service import ensure_registration_progress

debug_logger = logging.getLogger("telegram.update.debug")
logger = logging.getLogger(__name__)


async def process_telegram_update(update: dict) -> None:
    """
    Main Telegram update dispatcher with transaction management.

    Pipeline:
        1. Print the incoming Telegram update (debug tool).
        2. Extract normalized context.
        3. Execute stateless handlers (NO DB).
        4. If none match:
              - Open DB session
              - Load user state
              - REGISTRATION CHECKPOINT – send missing-field prompts in private chats
              - Execute stateful handlers
              - Commit on success / Rollback on error
        5. If still no handler matched, execute fallback handlers
        6. If fallback handlers don't match, the update is ignored.
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

    # --- 4) STATEFUL HANDLERS (WITH TRANSACTION MANAGEMENT) ---
    user_id = context.get("user_id")

    if not user_id:
        # No user_id means we can't load state; fall through to fallback handlers.
        pass
    else:
        async with AsyncSessionLocal() as db:
            try:
                repo = BotStateRepository(db)
                state_service = BotStateService(repo)
                context["user_state"] = await state_service.fetch_user_state(user_id)

                # ---------- REGISTRATION CHECKPOINT ----------
                # Only intervene for direct user messages in private chats.
                # The checkpoint will prompt for the next missing field.
                if (
                    is_user_message_in_private(context)
                    and context["update_type"] == "message"
                ):
                    registration_handled = await ensure_registration_progress(
                        db=db,
                        user_id=user_id,
                        chat_id=context["chat_id"],
                        username=context.get("username"),
                        telegram_first_name=context.get("first_name"),
                        telegram_last_name=context.get("last_name"),
                        user_state=context["user_state"],
                    )
                    if registration_handled:
                        return   # Prompt sent, stop processing this update
                # ---------------------------------------------

                for handler in STATEFUL_HANDLERS:
                    if await handler.match(context, db):
                        await handler.handle(context, db)
                        await db.commit()
                        return

                # If we reach here, no stateful handler matched.
                # Continue to fallback handlers below.

            except Exception as e:
                await db.rollback()
                logger.error(
                    f"Error processing update for user {user_id}: {e}",
                    exc_info=True,
                )
                # Don't return – fallback handlers may still be appropriate.

    # --- 5) FALLBACK HANDLERS (NO DB SESSION) ---
    for handler in FALLBACK_HANDLERS:
        if await handler.match(context, None):
            await handler.handle(context, None)
            return

    # --- 6) NO HANDLER MATCHED ---
    debug_logger.debug(
        f"No handler matched update type: {context['update_type']}"
    )