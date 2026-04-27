"""
HilfenUserRepository

This repository wraps the shared UserBaseRepository. It exists to keep the
Hilfen module decoupled from other modules should user management evolve
independently in the future.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from app.shared.repositories.user_base import UserBaseRepository


class HilfenUserRepository(UserBaseRepository):
    """
    Thin wrapper around UserBaseRepository.

    This class exists so the Hilfen module does not depend directly on
    the shared user repository structure and can introduce Hilfen-specific
    user logic later without changing other modules.
    """

    def __init__(self, db: AsyncSession):
        super().__init__(db)
