import re
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.models.user import User
from app.modules.eurobot.members.schemas.insert_request import BotInsertMemberRequest
from app.shared.repositories.user_base import UserBaseRepository
from app.core.exceptions import ServiceError

class InsertMemberService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = UserBaseRepository(db)

    def _clean_db_error(self, error_obj: Exception) -> str:
        """Helper to extract user-friendly messages from DB errors."""
        raw_msg = str(error_obj.orig) if hasattr(error_obj, 'orig') else str(error_obj)
        
        # PostgreSQL usually returns: "Duplicate... \nDETAIL: Key (x)=(y) already exists."
        if "DETAIL:" in raw_msg:
            # Split by DETAIL: and take the second part
            return raw_msg.split("DETAIL:", 1)[1].strip()
        
        # Fallback: remove the class name if it appears at the start (e.g., <class '...'>: )
        if raw_msg.strip().startswith("<class"):
            # Find the first colon and take everything after it
            parts = raw_msg.split(":", 1)
            if len(parts) > 1:
                return parts[1].strip()
                
        return raw_msg

    async def execute(self, payload: BotInsertMemberRequest) -> User:
        # 1. Prepare Data
        insert_data = payload.model_dump(exclude_unset=True)
        
        # Business Rule: Explicitly set chat_not_found to False
        insert_data["chat_not_found"] = False

        try:
            # 2. Call Repo
            new_user = await self.repo.create(insert_data)
            
            # 3. Commit Transaction
            await self.db.commit()
            return new_user

        except IntegrityError as e:
            await self.db.rollback()
            
            clean_message = self._clean_db_error(e)
            
            raise ServiceError(
                code="CONFLICT_OCCURRED",
                message=clean_message,
                status_code=409
            )
        except Exception as e:
            await self.db.rollback()
            raise e