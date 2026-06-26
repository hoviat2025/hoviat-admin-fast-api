from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update, select, or_
from app.shared.repositories.user_base import UserBaseRepository
from app.models.user import User

class HilfenUserRepository(UserBaseRepository):
    """
    Thin wrapper around UserBaseRepository. Maintains separation of concerns
    for Hilfen-specific database queries.
    """

    def __init__(self, db: AsyncSession):
        super().__init__(db)

    async def get_by_id(self, user_id: int) -> User | None:
        """Get user by Telegram user_id."""
        stmt = select(self.model).where(self.model.user_id == user_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create_user(self, user_id: int, username: str, nickname: str) -> User:
        """
        Create a new user with minimal required fields.
        """
        create_data = {
            "user_id": user_id,
            "username": username,
            "nickname": nickname if nickname else None,
            "counter": user_id,  # Set counter to match user_id explicitly
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
        """
        Updates the message IDs for Hilfen. Handles cases where both the main group
        and Hilfen message IDs are null, or where only the Hilfen fields are null.
        """
        # 1) Try to update when BOTH group and hilfen are NULL
        user = await self._update_if_both_empty(
            user_id, telegram_message_id, group_message_id,
            hilfen_message_id, hilfen_group_message_id
        )
        if user is not None:
            return user

        # 2) Otherwise try to update when only hilfen is NULL
        #    (group_message_id is already set, so we skip it to avoid overwriting)
        return await self._update_if_hilfen_empty(
            user_id, telegram_message_id,
            hilfen_message_id, hilfen_group_message_id
        )

    async def _update_if_both_empty(self, user_id, telegram_msg_id, group_msg_id, hilfen_msg_id, hilfen_group_msg_id):
        stmt = (
            update(User)
            .where(User.user_id == user_id)
            .where(or_(User.telegram_message_id.is_(None), User.telegram_message_id == telegram_msg_id))
            .where(User.group_message_id.is_(None))       # Guard: Only set if group is empty
            .where(User.hilfen_message_id.is_(None))      # Guard: Only set if hilfen is empty
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
            .where(or_(User.telegram_message_id.is_(None), User.telegram_message_id == telegram_msg_id))
            .where(User.hilfen_message_id.is_(None))      # Guard: Only set if hilfen is empty
            .values(
                telegram_message_id=telegram_msg_id,
                hilfen_message_id=hilfen_msg_id,
                hilfen_group_message_id=hilfen_group_msg_id,
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