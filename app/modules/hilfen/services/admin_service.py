# app/modules/hilfen/services/admin_service.py
"""
Admin authorization helpers for the Hilfen bot.

Currently uses a hardcoded set of user IDs. In the future this can be
replaced by a database check or an environment variable.
"""

from typing import final

# TODO: load from settings or DB
_ADMIN_USER_IDS: frozenset[int] = frozenset({2, 3, 4})


@final
class AdminService:
    """Stateless admin check."""

    @staticmethod
    def is_admin(user_id: int | None) -> bool:
        if user_id is None:
            return False
        return user_id in _ADMIN_USER_IDS