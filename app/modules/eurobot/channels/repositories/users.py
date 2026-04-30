from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.shared.repositories.user_base import UserBaseRepository

class UserMessageUpdateRepository(UserBaseRepository):
    
    async def set_message_ids_if_empty(
        self, 
        user_id: int, 
        telegram_message_id: str, 
        group_message_id: str,
        public_message_id: str,
        public_group_message_id: str,
        hilfen_message_id: str,
        hilfen_group_message_id: str
    ) -> User | None:
        """
        Updates ALL 6 message IDs for a user ONLY IF they are currently NULL.
        Returns the updated User object if successful.
        Returns None if the user didn't exist OR if the fields were not empty.
        """
        stmt = (
            update(User)
            .where(User.user_id == user_id)
            # --- THE "ONE MOTION" LOGIC ---
            # We check if the main IDs are NULL to ensure we don't overwrite existing data.
            .where(User.telegram_message_id.is_(None))
            .where(User.public_message_id.is_(None))
            .where(User.hilfen_message_id.is_(None))
            # ------------------------------
            .values(
                telegram_message_id=telegram_message_id,
                group_message_id=group_message_id,
                public_message_id=public_message_id,
                public_group_message_id=public_group_message_id,
                hilfen_message_id=hilfen_message_id,
                hilfen_group_message_id=hilfen_group_message_id
            )
            .returning(User)
        )

        result = await self.db.execute(stmt)
        
        # If the fields were not null (race condition lost), this returns None immediately
        return result.scalars().first()
