from sqlalchemy.ext.asyncio import AsyncSession


class BotStateRepository:
    """
    Repository responsible for reading and updating bot conversation state.

    The concrete storage implementation depends on the application's
    database schema.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_state(self, user_id: int) -> str | None:
        """
        Retrieve the stored state for a user.

        Replace with a SQLAlchemy query against the application's user table.
        """
        raise NotImplementedError("Bot state query not implemented.")

    async def update_state(self, user_id: int, new_state: str) -> None:
        """
        Persist a new state for the given user.

        Replace with a SQLAlchemy update statement.
        """
        raise NotImplementedError("Bot state update not implemented.")
