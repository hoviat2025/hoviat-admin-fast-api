from app.modules.hilfen.repositories.bot_state import BotStateRepository


class BotStateService:
    """
    Service layer for bot state management.

    Encapsulates transaction boundaries and domain logic around
    conversation state transitions.
    """

    def __init__(self, repo: BotStateRepository):
        self.repo = repo

    async def fetch_user_state(self, user_id: int) -> str | None:
        return await self.repo.get_state(user_id)

    async def update_user_state(self, user_id: int, new_state: str) -> None:
        await self.repo.update_state(user_id, new_state)
        await self.repo.db.commit()
