# app\modules\hilfen\repositories\user_repository.py
"""
HilfenUserRepository

This repository wraps the shared UserBaseRepository. It exists to keep the
Hilfen module decoupled from other modules should user management evolve
independently in the future.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update, select
from app.shared.repositories.user_base import UserBaseRepository
from app.models.user import User


class HilfenUserRepository(UserBaseRepository):
    """
    Thin wrapper around UserBaseRepository.

    This class exists so the Hilfen module does not depend directly on
    the shared user repository structure and can introduce Hilfen-specific
    user logic later without changing other modules.
    """

    def __init__(self, db: AsyncSession):
        super().__init__(db)

    async def get_by_id(self, user_id: int):
        """Get user by Telegram user_id."""
        stmt = select(self.model).where(self.model.user_id == user_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create_user(self, user_id: int, username: str, nickname: str) :
        """
        Create a new user with minimal required fields.
        
        Args:
            user_id: Telegram user ID
            username: Telegram username (can be None)
            first_name: Telegram first name
            last_name: Telegram last name
        """
        
        create_data = {
            "user_id": user_id,
            "username": username,
            "nickname": nickname if nickname else None,
            "counter": user_id,  # Using user_id as counter for simplicity
        }
        
        return await self.create(create_data)

    async def update_first_name(self, user_id: int, first_name: str) -> None:
        """Update user's first name."""
        stmt = (
            update(self.model)
            .where(self.model.user_id == user_id)
            .values(first_name=first_name)
        )
        await self.db.execute(stmt)

    async def update_last_name(self, user_id: int, last_name: str) -> None:
        """Update user's last name."""
        stmt = (
            update(self.model)
            .where(self.model.user_id == user_id)
            .values(last_name=last_name)
        )
        await self.db.execute(stmt)

    async def update_country(self, user_id: int, country: str) -> None:
        """Update user's country."""
        stmt = (
            update(self.model)
            .where(self.model.user_id == user_id)
            .values(country=country)
        )
        await self.db.execute(stmt)

    async def update_phone_number(self, user_id: int, phone_number: str) -> None:
        """Update user's phone number."""
        stmt = (
            update(self.model)
            .where(self.model.user_id == user_id)
            .values(phone_number=phone_number)
        )
        await self.db.execute(stmt)

    async def update_nickname(self, user_id: int, nickname: str) -> None:
        """Update user's nickname."""
        stmt = (
            update(self.model)
            .where(self.model.user_id == user_id)
            .values(nickname=nickname)
        )
        await self.db.execute(stmt)

    async def update_field(self, user_id: int, field_name: str, value: any) -> None:
        """Update a specific field for a user."""
        update_data = {field_name: value}
        stmt = (
            update(self.model)
            .where(self.model.user_id == user_id)
            .values(**update_data)
        )
        await self.db.execute(stmt)

    async def set_hilfen_message_ids_if_empty(
        self,
        user_id: int,
        telegram_message_id: str,
        group_message_id: str,
        hilfen_message_id: str,
        hilfen_group_message_id: str,
    ) -> User | None:
        # 1) Try to update when BOTH group and hilfen are NULL
        user = await self._update_if_both_empty(
            user_id, telegram_message_id, group_message_id,
            hilfen_message_id, hilfen_group_message_id
        )
        if user is not None:
            return user

        # 2) Otherwise try to update when only hilfen is NULL
        #    (group_message_id is already set, so we skip it)
        return await self._update_if_hilfen_empty(
            user_id, telegram_message_id,
            hilfen_message_id, hilfen_group_message_id
        )

    async def _update_if_both_empty(self, user_id, telegram_msg_id, group_msg_id, hilfen_msg_id, hilfen_group_msg_id):
        stmt = (
            update(User)
            .where(User.user_id == user_id)
            .where(User.group_message_id.is_(None))
            .where(User.hilfen_message_id.is_(None))
            .values(
                telegram_message_id=telegram_msg_id,
                group_message_id=group_msg_id,
                hilfen_message_id=hilfen_msg_id,
                hilfen_group_message_id=hilfen_group_msg_id,
            )
            .returning(User)
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def _update_if_hilfen_empty(self, user_id, telegram_msg_id, hilfen_msg_id, hilfen_group_msg_id):
        stmt = (
            update(User)
            .where(User.user_id == user_id)
            .where(User.hilfen_message_id.is_(None))
            .values(
                telegram_message_id=telegram_msg_id,
                hilfen_message_id=hilfen_msg_id,
                hilfen_group_message_id=hilfen_group_msg_id,
            )
            .returning(User)
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()
    
    
    async def set_admin_message_ids_if_empty(
        self,
        user_id: int,
        telegram_message_id: str,
        group_message_id: str,
        admin_message_id: str,
        admin_group_message_id: str,
    ) -> User | None:
        # 1) Try to update when BOTH group and admin are NULL
        user = await self._update_if_both_empty(
            user_id, telegram_message_id, group_message_id,
            admin_message_id, admin_group_message_id
        )
        if user is not None:
            return user

        # 2) Otherwise try to update when only admin is NULL
        #    (group_message_id is already set, so we skip it)
        return await self._update_if_admin_empty(
            user_id, telegram_message_id,
            admin_message_id, admin_group_message_id
        )

    async def _update_if_both_empty(self, user_id, telegram_msg_id, group_msg_id, admin_msg_id, admin_group_msg_id):
        stmt = (
            update(User)
            .where(User.user_id == user_id)
            .where(User.group_message_id.is_(None))
            .where(User.admin_message_id.is_(None))
            .values(
                telegram_message_id=telegram_msg_id,
                group_message_id=group_msg_id,
                admin_message_id=admin_msg_id,
                admin_group_message_id=admin_group_msg_id,
            )
            .returning(User)
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def _update_if_admin_empty(self, user_id, telegram_msg_id, admin_msg_id, admin_group_msg_id):
        stmt = (
            update(User)
            .where(User.user_id == user_id)
            .where(User.admin_message_id.is_(None))
            .values(
                telegram_message_id=telegram_msg_id,
                admin_message_id=admin_msg_id,
                admin_group_message_id=admin_group_msg_id,
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
