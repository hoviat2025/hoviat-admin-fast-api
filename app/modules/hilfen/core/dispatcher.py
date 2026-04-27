import json
import logging
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.modules.hilfen.core.context_extractor import extract_context
from app.modules.hilfen.handlers.registry import (
    STATELESS_HANDLERS,
    STATEFUL_HANDLERS,
)
from app.modules.hilfen.repositories.bot_state import BotStateRepository
from app.modules.hilfen.services.state_service import BotStateService

# Debug logger for raw Telegram updates
debug_logger = logging.getLogger("telegram.update.debug")


async def process_telegram_update(update: dict) -> None:
    """
    Main Telegram update dispatcher with lazy DB initialization.

    Pipeline:
        1. Print the incoming Telegram update (debug tool).
        2. Extract normalized context.
        3. Execute stateless handlers (NO DB).
        4. If none match:
              - Open DB session
              - Load user state
              - Execute stateful handlers
    """

    # --- 1) PRINT RAW TELEGRAM UPDATE (debugging trick) ---
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

    # --- 4) STATEFUL HANDLERS (REQUIRES DB SESSION) ---
    user_id = context.get("user_id")

    if not user_id:
        return

    async with AsyncSessionLocal() as db:  # type AsyncSession
        repo = BotStateRepository(db)
        state_service = BotStateService(repo)

        context["user_state"] = await state_service.fetch_user_state(user_id)

        for handler in STATEFUL_HANDLERS:
            if await handler.match(context, db):
                await handler.handle(context, db)
                return
