import logging
from typing import List, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.core.exceptions import ServiceError
from app.models.user import User
from app.modules.hilfen.members.schemas.response import HilfenUserResponse

logger = logging.getLogger(__name__)

class BulkReadMembersService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def execute(self, user_ids: List[int]) -> Dict[str, Optional[HilfenUserResponse]]:
        # 1. Optimization: Early return if list is empty (though Pydantic min_items=1 handles this)
        if not user_ids:
            return {}

        # 2. Optimization: Remove duplicates to reduce DB load
        unique_ids = list(set(user_ids))

        try:
            # 3. Perform Bulk Query
            stmt = select(User).where(User.user_id.in_(unique_ids))
            result = await self.db.execute(stmt)
            found_users = result.scalars().all()

        except SQLAlchemyError as e:
            # 4. Production Logging: Log the actual DB error
            logger.error(f"Database error during bulk read: {str(e)}")
            raise ServiceError(
                code="DB_ERROR",
                message="Database unavailable",
                status_code=500
            )

        # 5. Create Lookup Map
        user_map = {u.user_id: u for u in found_users}

        response_data = {}

        # 6. Build response maintaining the requested ID list
        for uid in user_ids:
            user_obj = user_map.get(uid)
            key = str(uid)

            if user_obj:
                response_data[key] = HilfenUserResponse.from_db_model(user_obj)
            else:
                response_data[key] = None

        return response_data