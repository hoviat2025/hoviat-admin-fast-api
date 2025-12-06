from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update
from app.models.user import User
from app.modules.eurobot.schemas import BotUpdateMemberRequest
from app.core.exceptions import ServiceError

class EurobotService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def update_member(self, payload: BotUpdateMemberRequest) -> User:
        # exclude_unset=True is CRITICAL here. 
        # It ensures that if the bot does NOT send "score", we don't overwrite the existing score with Null.
        update_data = payload.model_dump(exclude_unset=True, exclude={"user_id"})

        if not update_data:
            raise ServiceError(code="INVALID_INPUT", message="No fields provided for update", status_code=422)

        stmt = (
            update(User)
            .where(User.user_id == payload.user_id)
            .values(**update_data)
            .returning(User)
        )

        result = await self.db.execute(stmt)
        updated_user = result.scalars().first()

        if not updated_user:
            raise ServiceError(
                code="USERID_NOT_FOUND", 
                message=f"No user exists with user_id {payload.user_id}",
                status_code=404
            )
        
        await self.db.commit()
        return updated_user