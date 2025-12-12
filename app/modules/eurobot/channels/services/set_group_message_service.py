from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.shared.repositories.user_base import UserBaseRepository
from app.core.exceptions import ServiceError
from app.modules.eurobot.channels.schemas.set_group_message_request import SetGroupMessageRequest

class SetGroupMessageService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = UserBaseRepository(db)

    async def execute(self, payload: SetGroupMessageRequest) -> User:
        """
        Updates the user's telegram and group message IDs based on a webhook payload.
        """
        user_id = payload.extracted_user_id
        
        # FIX: Convert integers to strings because DB columns are VARCHAR
        telegram_msg_id = str(payload.original_update.message.forward_origin.message_id)
        group_msg_id = str(payload.original_update.message.message_id)

        update_data = {
            "telegram_message_id": telegram_msg_id,
            "group_message_id": group_msg_id
        }

        # Perform Update
        updated_user = await self.repo.update(
            user_id=user_id,
            update_data=update_data
        )

        if not updated_user:
            raise ServiceError(
                code="USER_NOT_FOUND",
                message=f"User {user_id} not found",
                status_code=404
            )

        # Commit Transaction
        await self.db.commit()
        
        return updated_user