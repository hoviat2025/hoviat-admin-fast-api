# app/modules/hilfen/repositories/bot_state.py
from sqlalchemy.ext.asyncio import AsyncSession

class BotStateRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_state(self, user_id: int):
        return None  # no persisted state for now

    async def update_state(self, user_id: int, new_state: str):
        pass
