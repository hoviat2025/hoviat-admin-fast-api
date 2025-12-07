from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.shared.repositories.user_base import UserBaseRepository
from app.core.exceptions import ServiceError

class GetMemberService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = UserBaseRepository(db)

    async def execute(self, user_id: int) -> User:
        user = await self.repo.get_by_id(user_id)
        if not user:
            raise ServiceError(
                code="USERID_NOT_FOUND",
                message=f"No user exists with user_id {user_id}",
                status_code=404
            )
        return user