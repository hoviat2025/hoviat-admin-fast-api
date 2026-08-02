from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update, select, or_
from app.shared.repositories.user_base import UserBaseRepository
from app.models.user import User

class UserMessageUpdateRepository(UserBaseRepository):
    """
    Thin wrapper around UserBaseRepository for Eurobot's message channels.
    """

    def __init__(self, db: AsyncSession):
        super().__init__(db)

    async def get_by_id(self, user_id: int) -> User | None:
        stmt = select(self.model).where(self.model.user_id == user_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def set_message_ids_if_empty(
        self,
        user_id: int,
        telegram_message_id: str,
        group_message_id: str,
        public_message_id: str,
        public_group_message_id: str,
    ) -> User | None:
        """
        Updates the message IDs for Eurobot's Public Channel. Handles cases where both
        the main group and Public message IDs are null, or where only the Public fields are null.
        """
        # 1) Try to update when BOTH group and public are NULL
        user = await self._update_if_both_empty(
            user_id, telegram_message_id, group_message_id,
            public_message_id, public_group_message_id
        )
        if user is not None:
            return user

        # 2) Otherwise try to update when only public is NULL
        #    (group_message_id is already set, so we skip it to avoid overwriting)
        return await self._update_if_public_empty(
            user_id, telegram_message_id,
            public_message_id, public_group_message_id
        )

    async def _update_if_both_empty(self, user_id, telegram_msg_id, group_msg_id, public_msg_id, public_group_msg_id):
        stmt = (
            update(User)
            .where(User.user_id == user_id)
            .where(or_(User.telegram_message_id.is_(None), User.telegram_message_id == telegram_msg_id))
            .where(User.group_message_id.is_(None))       # Guard: Only set if group is empty
            .where(User.public_message_id.is_(None))      # Guard: Only set if public is empty
            .values(
                telegram_message_id=telegram_msg_id,
                group_message_id=group_msg_id,
                public_message_id=public_msg_id,
                public_group_message_id=public_group_msg_id,
            )
            .returning(User)
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def _update_if_public_empty(self, user_id, telegram_msg_id, public_msg_id, public_group_msg_id):
        stmt = (
            update(User)
            .where(User.user_id == user_id)
            .where(or_(User.telegram_message_id.is_(None), User.telegram_message_id == telegram_msg_id))
            .where(User.public_message_id.is_(None))      # Guard: Only set if public is empty
            .values(
                telegram_message_id=telegram_msg_id,
                public_message_id=public_msg_id,
                public_group_message_id=public_group_msg_id,
            )
            .returning(User)
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()

    @property
    def model(self):
        """Get the User model class."""
        from app.models.user import User
        return User