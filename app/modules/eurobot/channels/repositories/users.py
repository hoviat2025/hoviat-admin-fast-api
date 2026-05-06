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
    ) -> User | None:
        # 1) Try to update when BOTH group and public are NULL
        user = await self._update_if_both_empty(
            user_id, telegram_message_id, group_message_id,
            public_message_id, public_group_message_id
        )
        if user is not None:
            return user

        # 2) Otherwise try to update when only public is NULL
        #    (group_message_id is already set, so we skip it)
        return await self._update_if_public_empty(
            user_id, telegram_message_id,
            public_message_id, public_group_message_id
        )

    async def _update_if_both_empty(self, user_id, telegram_msg_id, group_msg_id,
                                    public_msg_id, public_group_msg_id):
        stmt = (
            update(User)
            .where(User.user_id == user_id)
            .where(User.group_message_id.is_(None))
            .where(User.public_message_id.is_(None))
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

    async def _update_if_public_empty(self, user_id, telegram_msg_id,
                                      public_msg_id, public_group_msg_id):
        stmt = (
            update(User)
            .where(User.user_id == user_id)
            .where(User.public_message_id.is_(None))
            .values(
                telegram_message_id=telegram_msg_id,
                public_message_id=public_msg_id,
                public_group_message_id=public_group_msg_id,
            )
            .returning(User)
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()