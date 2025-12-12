from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.shared.repositories.user_base import UserBaseRepository
from app.core.exceptions import ServiceError
from app.modules.eurobot.channels.schemas.set_public_message_request import SetPublicMessageRequest

class SetPublicMessageService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = UserBaseRepository(db)

    async def execute(self, payload: SetPublicMessageRequest) -> User:
        # 1. Extract IDs and CONVERT TO STRING (Vital for DB match)
        
        # The ID to search for (The Main Channel Message ID)
        lookup_msg_id = str(payload.original_update.message.external_reply.message_id)
        
        # The IDs to update
        public_msg_id = str(payload.original_update.message.forward_origin.message_id)
        public_group_msg_id = str(payload.original_update.message.message_id)

        # 2. Find the User
        user = await self.repo.get_by_telegram_message_id(lookup_msg_id)
        
        if not user:
            # 404 if we can't find which user owns that Main Channel post
            raise ServiceError(
                code="USER_NOT_FOUND",
                message=f"No user found with telegram_message_id: {lookup_msg_id}",
                status_code=404
            )

        # 3. Update the User
        update_data = {
            "public_message_id": public_msg_id,
            "public_group_message_id": public_group_msg_id
        }

        updated_user = await self.repo.update(
            user_id=user.user_id,
            update_data=update_data
        )

        # 4. Commit
        await self.db.commit()
        
        return updated_user