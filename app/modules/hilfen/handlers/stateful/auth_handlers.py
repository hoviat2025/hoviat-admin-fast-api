# app/modules/hilfen/handlers/stateful/auth_handlers.py
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.hilfen.core.base_handler import BaseHandler
from app.modules.hilfen.repositories.user_repository import HilfenUserRepository
from app.modules.hilfen.services.telegram_service import send_message
from app.modules.hilfen.services.registration_service import ensure_registration_progress


class StartCommandHandler(BaseHandler):
    """
    Handles the /start command.

    - For an existing user: sends a welcome‑back message.
    - For a **new** user: the registration checkpoint in the dispatcher already
      created the record and prompted for the country; this handler therefore
      does nothing in that case.
    """

    async def match(self, context: dict, db: AsyncSession) -> bool:
        text = context.get("text") or ""
        return text.startswith("/start")

    async def handle(self, context: dict, db: AsyncSession) -> None:
        chat_id = context.get("chat_id")
        user_id = context.get("user_id")

        user_repo = HilfenUserRepository(db)
        user = await user_repo.get_by_id(user_id)

        if user:
            # Registration already complete – just greet.
            greeting_name = user.first_name or "there"
            await send_message(chat_id, f"Hi {greeting_name}! Welcome back!")
            return

        # New user – the registration checkpoint (in the dispatcher) already
        # handled the creation + country prompt.  This branch is only reached
        # if for some reason the checkpoint didn't run; delegate to it once more
        # as a safety net.
        await ensure_registration_progress(
            db=db,
            user_id=user_id,
            chat_id=chat_id,
            chat_type="private",
            username=context.get("username"),
            telegram_first_name=context.get("first_name"),
            telegram_last_name=context.get("last_name"),
            user_state=context.get("user_state"),
        )