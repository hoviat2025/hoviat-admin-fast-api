from abc import ABC, abstractmethod
from sqlalchemy.ext.asyncio import AsyncSession


class BaseHandler(ABC):
    """
    Base interface for all Telegram handlers.

    Handlers are divided into two groups:
        - Stateless handlers
        - Stateful handlers

    Each handler decides if it should process an update via `match`.
    """

    @abstractmethod
    async def match(self, context: dict, db: AsyncSession) -> bool:
        """
        Determine whether this handler should process the update.
        """
        raise NotImplementedError

    @abstractmethod
    async def handle(self, context: dict, db: AsyncSession) -> None:
        """
        Execute the handler logic.
        """
        raise NotImplementedError
