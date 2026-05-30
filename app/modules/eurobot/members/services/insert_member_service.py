import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

# Core & Models
from app.models.user import User
from app.shared.repositories.user_base import UserBaseRepository
from app.core.exceptions import ServiceError

# Schemas
from app.modules.eurobot.members.schemas.insert_request import BotInsertMemberRequest

# --- ADDED IMPORTS ---
from app.modules.eurobot.channels.services.update_channel_post_service import UpdateChannelPostService
from app.modules.eurobot.channels.schemas.update_post_request import UpdateChannelPostRequest

logger = logging.getLogger(__name__)

class InsertMemberService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = UserBaseRepository(db)

    def _clean_db_error(self, error_obj: Exception) -> str:
        """Helper to extract user-friendly messages from DB errors."""
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
        insert_data = payload.model_dump(exclude_unset=True)
        
        # Business Rule: Explicitly set chat_not_found to False
        insert_data["chat_not_found"] = False

        try:
            # 2. Call Repo (Creates the user object in session)
            new_user = await self.repo.create(insert_data)
            
            # 3. Commit Transaction
            # This saves the user to the DB so the UpdateChannelPostService can access it.
            await self.db.commit()
            
            # Refresh ensures the instance is up-to-date and attached to the session
            # (useful if the DB triggers updated default timestamps, etc.)
            await self.db.refresh(new_user)

            # --- 4. Call Update Channel Service ---
            try:
                # update_service = UpdateChannelPostService(self.db)
                
                # # We use new_user.user_id (which you confirmed is the field name)
                # update_payload = UpdateChannelPostRequest(user_id=new_user.user_id)
                
                # # Execute the update. 
                # # The service returns the updated user object (with sync timestamps), so we update our reference.
                # new_user = await update_service.execute(update_payload)
                
            except Exception as e:
                # If the channel update fails, we log it but do NOT rollback the User creation.
                # The user was successfully created in step 3.
                logger.error(f"User {new_user.user_id} created, but failed to update channel post: {e}")
                
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