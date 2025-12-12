from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.shared.repositories.user_base import UserBaseRepository
from app.core.exceptions import ServiceError

class GetMemberByMessageService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = UserBaseRepository(db)

    async def execute(self, public_message_id: int) -> User:
        # Convert int to string for DB lookup (since columns are likely VARCHAR)
        msg_id_str = str(public_message_id)
        
        user = await self.repo.get_by_public_message_id(msg_id_str)
        
        if not user:
            raise ServiceError(
                code="MESSAGE_NOT_FOUND",
                message=f"No user found with public_message_id {public_message_id}",
                status_code=404
            )
            
        return user