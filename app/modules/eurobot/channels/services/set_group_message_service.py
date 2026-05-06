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
        self.hilfen_repo = HilfenUserRepository(db)             # handles hilfen & admin IDs

    async def execute(self, payload: SetGroupMessageRequest) -> User:
        """
        Stages the main message mapping (user_id + group_message_id) and then
        independently attempts to write *each* complete sub-message group
        (public, hilfen, admin) into the main User table – all in one transaction.

        Each write uses the “if empty” pattern: only fields that are still NULL
        in the User table are overwritten. This guarantees that whichever
        parallel process arrives first wins and no data is lost.
        """
        user_id = payload.extracted_user_id

        # 1. Convert Telegram IDs to integers for the staging table.
        telegram_msg_id_int = int(payload.original_update.message.forward_origin.message_id)
        group_msg_id_int = int(payload.original_update.message.message_id)

        # 2. Upsert the main (user + group) part of the staging row.
        #    This creates the row if it doesn't exist and always updates
        #    user_id + group_message_id.
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
            hilfen_result = await self.hilfen_repo.set_hilfen_message_ids_if_empty(
                user_id=staging_row.user_id,
                telegram_message_id=str(telegram_msg_id_int),
                group_message_id=str(staging_row.group_message_id),
                hilfen_message_id=str(staging_row.hilfen_message_id),
                hilfen_group_message_id=str(staging_row.hilfen_group_message_id),
            )
            if hilfen_result is not None:
                updated_user = hilfen_result

        # ------------------------------------------------------------
        # 5. Admin sub‑messages
        # ------------------------------------------------------------
        if (
            staging_row.admin_message_id is not None
            and staging_row.admin_group_message_id is not None
        ):
            admin_result = await self.hilfen_repo.set_admin_message_ids_if_empty(
                user_id=staging_row.user_id,
                telegram_message_id=str(telegram_msg_id_int),
                group_message_id=str(staging_row.group_message_id),
                admin_message_id=str(staging_row.admin_message_id),
                admin_group_message_id=str(staging_row.admin_group_message_id),
            )
            if admin_result is not None:
                updated_user = admin_result

        # ------------------------------------------------------------
        # 6. Commit the whole transaction
        # ------------------------------------------------------------
        await self.db.commit()

        # ------------------------------------------------------------
        # 7. Return the most recently updated User, or the current state.
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