from sqlalchemy import select
from typing import List
from app.shared.repositories.user_base import UserBaseRepository
from app.models.user import User

# Inherits from Base, so it automatically has 'get_by_id' too!
class AdminUserRepository(UserBaseRepository):
    
    async def get_all_users(self, limit: int = 10, offset: int = 0) -> List[User]:
        """
        Admin specific: List users with pagination.
        """
        query = select(User).limit(limit).offset(offset)
        result = await self.db.execute(query)
        return result.scalars().all()