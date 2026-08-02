from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.modules.eurobot.members.schemas.update_request import BotUpdateMemberRequest
from app.modules.eurobot.members.schemas.bot_user_dto import BotUserResponse
from app.modules.eurobot.members.schemas.bulk_update_request import (
    BulkUpdateResultData, 
    BulkUpdateSuccessItem, 
    BulkUpdateFailedItem
)
from app.modules.eurobot.members.services.update_member_service import UpdateMemberService
from app.core.exceptions import ServiceError

# Standardized batch size threshold
BATCH_LIMIT = 20

class BulkUpdateMembersService:
    def __init__(self, db: AsyncSession):
        self.db = db
        # Reuse existing update logic to maintain consistency
        self.single_update_service = UpdateMemberService(db)

    async def execute(self, payload: List[BotUpdateMemberRequest]) -> BulkUpdateResultData:
        successful = []
        failed = []

        for index, user_data in enumerate(payload):
            # 1. Enforce batch-size cap to protect gateway limits and prevent timeouts
            if index >= BATCH_LIMIT:
                failed.append(BulkUpdateFailedItem(
                    index=index,
                    code="CONFLICT_OCCURRED",
                    message=f"Too many requests in a single batch. Only the first {BATCH_LIMIT} are processed. Please retry."
                ))
                continue

            try:
                # 2. Execute Single Update (Repo update + Commit happens here)
                updated_user = await self.single_update_service.execute(user_data)

                # 3. Add to Success List (Convert ORM to Pydantic DTO)
                successful.append(BulkUpdateSuccessItem(
                    index=index,
                    user_id=user_data.user_id,
                    data=BotUserResponse.model_validate(updated_user)
                ))

            except ServiceError as e:
                # 4. Handle Logic Errors (e.g. User Not Found)
                await self.db.rollback()
                failed.append(BulkUpdateFailedItem(
                    index=index,
                    code=e.code,
                    message=e.message
                ))

            except IntegrityError as e:
                # 5. Handle DB Constraint Errors (e.g. Duplicates)
                await self.db.rollback()
                # Try to get clean error message
                error_msg = str(e.orig) if hasattr(e, 'orig') else str(e)
                failed.append(BulkUpdateFailedItem(
                    index=index,
                    code="CONFLICT_OCCURRED",
                    message=f"Database conflict: {error_msg}"
                ))

            except Exception as e:
                # 6. Handle Unexpected Errors
                await self.db.rollback()
                failed.append(BulkUpdateFailedItem(
                    index=index,
                    code="INTERNAL_ERROR",
                    message=str(e)
                ))

        # Return the clean data object, letting Router handle the wrapping
        return BulkUpdateResultData(
            successful=successful,
            failed=failed
        )