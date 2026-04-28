# app\modules\hilfen\repositories\bot_state.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.models.user import User

class BotStateRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_state(self, user_id: int) -> str | None:
        """Get the current state of a user."""
        stmt = select(User.hilfen_state).where(User.user_id == user_id)
        result = await self.db.execute(stmt)
        state = result.scalar_one_or_none()
        return state

    async def update_state(self, user_id: int, new_state: str | None) -> None:
        """Update the user's state."""
        if new_state is None:
            # Clear the state
            stmt = (
                update(User)
                .where(User.user_id == user_id)
                .values(hilfen_state=None)
            )
        else:
            stmt = (
                update(User)
                .where(User.user_id == user_id)
                .values(hilfen_state=new_state)
            )
        await self.db.execute(stmt)

    async def get_user_by_id(self, user_id: int) -> User | None:
        """Get user by user_id."""
        stmt = select(User).where(User.user_id == user_id)
        result = await self.db.execute(stmt)
        return result.scalars().first()
