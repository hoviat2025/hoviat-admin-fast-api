from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.modules.hilfen.core.context_extractor import extract_context
from app.modules.hilfen.handlers.registry import (
    STATELESS_HANDLERS,
    STATEFUL_HANDLERS,
)
from app.modules.hilfen.repositories.bot_state import BotStateRepository
from app.modules.hilfen.services.state_service import BotStateService


async def process_telegram_update(update: dict) -> None:
    """
    Main Telegram update dispatcher.

    Execution pipeline:

        1. Extract normalized context
        2. Execute stateless handlers (NO database session created)
        3. If no stateless handler matched:
            - Open database session
            - Load user state (if user exists)
            - Execute stateful handlers

    This design prevents unnecessary database connections for purely
    stateless commands (e.g. /start, /sam).
    """

    context = extract_context(update)

    if context["update_type"] == "unknown":
        return

    # ---------------------------------------------------------
    # 1️⃣  Execute Stateless Handlers (No DB Session)
    # ---------------------------------------------------------
    for handler in STATELESS_HANDLERS:
        if await handler.match(context, None):
            await handler.handle(context, None)
            return

    # ---------------------------------------------------------
    # 2️⃣  Execute Stateful Handlers (Requires DB)
    # ---------------------------------------------------------
    user_id = context.get("user_id")

    # If no user_id exists, stateful handlers cannot operate
    if not user_id:
        return

    # Lazily create DB session only now
    async with AsyncSessionLocal() as db:  # type: AsyncSession
        repo = BotStateRepository(db)
        state_service = BotStateService(repo)

        context["user_state"] = await state_service.fetch_user_state(user_id)

        for handler in STATEFUL_HANDLERS:
            if await handler.match(context, db):
                await handler.handle(context, db)
                return
