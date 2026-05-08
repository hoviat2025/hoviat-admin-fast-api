import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.models.user import User
from app.modules.eurobot.members.schemas.insert_request import BotInsertMemberRequest
from app.shared.repositories.user_base import UserBaseRepository
from app.core.exceptions import ServiceError

# --- ADDED IMPORTS ---
from app.modules.eurobot.channels.services.update_channel_post_service import UpdateChannelPostService
from app.modules.eurobot.channels.schemas.update_post_request import UpdateChannelPostRequest

logger = logging.getLogger(__name__)

class UpsertMemberService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = UserBaseRepository(db)

    def _clean_db_error(self, error_obj: Exception) -> str:
        """Extract user-friendly message from DB error."""
        raw_msg = str(error_obj.orig) if hasattr(error_obj, 'orig') else str(error_obj)
        if "DETAIL:" in raw_msg:
            return raw_msg.split("DETAIL:", 1)[1].strip()
        if raw_msg.strip().startswith("<class"):
            parts = raw_msg.split(":", 1)
            if len(parts) > 1:
                return parts[1].strip()
        return raw_msg

    async def execute(self, payload: BotInsertMemberRequest) -> User:
        # 1. Prepare Data
        upsert_data = payload.model_dump(exclude_unset=True)
        
        # Business Rule: Reset chat_not_found
        upsert_data["chat_not_found"] = False

        try:
            # 2. Call Repo (Upsert)
            user = await self.repo.upsert(upsert_data)
            
            # 3. Commit
            # Save the upsert changes to the DB first.
            await self.db.commit()

            # Refreshing ensures the object is bound to the session and up-to-date
            # before passing it to the next service.
            await self.db.refresh(user)

            # --- 4. Call Update Channel Service ---
            try:
                update_service = UpdateChannelPostService(self.db)
                
                # Execute the update. 
                # This syncs the user with the Telegram channel.
                user = await update_service.execute(user.user_id)

            except Exception as e:
                # Log the error but do NOT rollback the Upsert.
                # The user data is safe in the DB.
                logger.error(f"User {user.user_id} upserted, but failed to update channel post: {e}")

            return user

        except IntegrityError as e:
            # This catches conflicts on columns OTHER than user_id (e.g. counter)
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