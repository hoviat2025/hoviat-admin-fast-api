from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.modules.eurobot.members.schemas.update_request import BotUpdateMemberRequest
from app.shared.repositories.user_base import UserBaseRepository # Import Repo
from app.core.exceptions import ServiceError

class UpdateMemberService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = UserBaseRepository(db) # Use the Repo

    async def execute(self, payload: BotUpdateMemberRequest) -> User:
        # 1. Business Logic: Prepare Data
        update_data = payload.model_dump(exclude_unset=True, exclude={"user_id"})

        if not update_data:
            raise ServiceError(code="INVALID_INPUT", message="No fields provided for update", status_code=422)

        # 2. Data Access: Call the Repo (Service doesn't know SQL)
        updated_user = await self.repo.update(
            user_id=payload.user_id, 
            update_data=update_data
        )

        # 3. Business Logic: Check Existance
        if not updated_user:
            raise ServiceError(
                code="USERID_NOT_FOUND", 
                message=f"No user exists with user_id {payload.user_id}",
                status_code=404
            )
        
        # 4. Transaction Management: Commit
        # The Service decides "The work is done, save it."
        await self.db.commit()
        
        # 5. Since you have 'expire_on_commit=False', you usually don't need refresh 
        # unless DB triggers changed data.
        return updated_user