# app\modules\hilfen\services\state_service.py
"""
State service for managing user states in the Hilfen bot.

This service handles state transitions and provides a clean interface
for handlers to interact with user states.
"""

from app.modules.hilfen.repositories.bot_state import BotStateRepository


class BotStateService:
    def __init__(self, repo: BotStateRepository):
        self.repo = repo

    async def fetch_user_state(self, user_id: int) -> str | None:
        """
        Get the current state of a user.
        
        Returns:
            The user's current state string, or None if no state is set.
        """
        return await self.repo.get_state(user_id)

    async def update_user_state(self, user_id: int, new_state: str | None) -> None:
        """
        Update a user's state.
        
        Args:
            user_id: Telegram user ID
            new_state: New state string, or None to clear the state
        """
        await self.repo.update_state(user_id, new_state)

    async def get_user_data(self, user_id: int):
        """
        Get user data including state.
        
        Returns:
            User object or None if user doesn't exist
        """
        return await self.repo.get_user_by_id(user_id)
