from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.core.exceptions import ServiceError
from app.modules.eurobot.channels.schemas.set_group_message_request import SetGroupMessageRequest

from app.modules.eurobot.channels.repositories.stage_message_ids import TelegramMessageRepository
from app.modules.eurobot.channels.repositories.users import UserMessageUpdateRepository
from app.modules.hilfen.repositories.user_repository import HilfenUserRepository

class SetGroupMessageService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.stage_repo = TelegramMessageRepository(db)
        self.public_repo = UserMessageUpdateRepository(db)       # handles public IDs
        self.hilfen_repo = HilfenUserRepository(db)             # handles hilfen IDs

    async def execute(self, payload: SetGroupMessageRequest) -> User:
        """
        Stages the main message mapping (user_id + group_message_id) and then
        independently attempts to write each complete sub-message group
        (public, hilfen) into the main User table – all in one transaction.

        Each repository update uses the strict "if empty" pattern. Whichever
        webhook arrives first sets the shared main IDs, and late-arriving webhooks
        safely update only their respective sub-columns.
        """
        user_id = payload.extracted_user_id

        # 1. Convert Telegram IDs to integers for the staging table.
        telegram_msg_id_int = int(payload.original_update.message.forward_origin.message_id)
        group_msg_id_int = int(payload.original_update.message.message_id)

        # 2. Upsert the main (user + group) part of the staging row.
        staging_row = await self.stage_repo.upsert_user_mapping(
            telegram_message_id=telegram_msg_id_int,
            user_id=user_id,
            group_message_id=group_msg_id_int,
        )

        updated_user = None

        # ------------------------------------------------------------
        # 3. Public sub‑messages
        # ------------------------------------------------------------
        if (
            staging_row.public_message_id is not None
            and staging_row.public_group_message_id is not None
        ):
            # All public staging IDs are present → try to write them into
            # the User table (only if the corresponding User columns are empty).
            updated_user = await self.public_repo.set_message_ids_if_empty(
                user_id=user_id,
                telegram_message_id=str(telegram_msg_id_int),
                group_message_id=str(staging_row.group_message_id),
                public_message_id=str(staging_row.public_message_id),
                public_group_message_id=str(staging_row.public_group_message_id),
            )

        # ------------------------------------------------------------
        # 4. Hilfen sub‑messages
        # ------------------------------------------------------------
        if (
            staging_row.hilfen_message_id is not None
            and staging_row.hilfen_group_message_id is not None
        ):
            # All hilfen staging IDs are present → try to write them into
            # the User table. We pass Hilfen IDs as native int() to align with the SQL BIGINT column types.
            hilfen_result = await self.hilfen_repo.set_hilfen_message_ids_if_empty(
                user_id=staging_row.user_id,
                telegram_message_id=str(telegram_msg_id_int),
                group_message_id=str(staging_row.group_message_id),
                hilfen_message_id=int(staging_row.hilfen_message_id),          # Changed from str() to int()
                hilfen_group_message_id=int(staging_row.hilfen_group_message_id), # Changed from str() to int()
            )
            if hilfen_result is not None:
                updated_user = hilfen_result

        # ------------------------------------------------------------
        # 5. Commit the whole transaction
        # ------------------------------------------------------------
        await self.db.commit()

        # ------------------------------------------------------------
        # 6. Return the most recently updated User, or the current state.
        # ------------------------------------------------------------
        if updated_user:
            return updated_user

        # No update happened (either staging incomplete or all User columns
        # were already set by a parallel process).
        existing_user = await self.hilfen_repo.get_by_id(user_id)
        if not existing_user:
            raise ServiceError(
                code="USER_NOT_FOUND",
                message=f"User {user_id} not found",
                status_code=404,
            )
        return existing_user