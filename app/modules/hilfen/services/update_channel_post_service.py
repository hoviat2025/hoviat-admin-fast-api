# app\modules\hilfen\services\update_channel_post_service.py
"""
Proxy service to update channel post after user registration.

This service acts as a proxy to the eurobot module's update_channel_post service.
It ensures the same functionality while keeping modules decoupled.
"""

import logging
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.core.exceptions import ServiceError

logger = logging.getLogger(__name__)


class UpdateChannelPostService:
    """
    Proxy service that delegates to the eurobot module's update_channel_post service.
    
    This ensures the same business logic is applied while maintaining module separation.
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db

    async def execute(self, user_id: int) -> User:
        """
        Execute the channel post update for a user by delegating to eurobot service.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            Updated user object
            
        Raises:
            ServiceError: If user not found or update fails
        """
        try:
            # Import the eurobot service and schema
            from app.modules.eurobot.channels.services.update_channel_post_service import (
                UpdateChannelPostService as EurobotUpdateChannelPostService
            )
            from app.modules.eurobot.channels.schemas.update_post_request import (
                UpdateChannelPostRequest
            )
            
            # Create the eurobot service instance
            eurobot_service = EurobotUpdateChannelPostService(self.db)
            
            # Prepare the request payload
            update_payload = UpdateChannelPostRequest(user_id=user_id)
            
            # Execute the eurobot service
            updated_user = await eurobot_service.execute(update_payload)
            
            logger.info(f"Channel post update completed for user {user_id}")
            return updated_user
            
        except ImportError as e:
            logger.error(f"Failed to import eurobot update_channel_post service: {e}")
            raise ServiceError(
                code="SERVICE_UNAVAILABLE",
                message="Channel update service is currently unavailable",
                status_code=503
            )
        except Exception as e:
            logger.error(f"Failed to update channel post for user {user_id}: {e}")
            # Re-raise the exception to be handled by the caller
            raise
