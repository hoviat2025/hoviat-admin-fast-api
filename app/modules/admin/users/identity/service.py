from typing import List
from app.modules.admin.users.repository import AdminUserRepository
from app.models.user import User

class IdentityService:
    def __init__(self, repo: AdminUserRepository):
        self.repo = repo

    async def list_users(self, limit: int) -> List[User]:
        # Here is where you might eventually add logic like:
        # "Log that the admin viewed the list"
        # "Filter out deleted users"
        return await self.repo.get_all_users(limit=limit)