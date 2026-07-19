from typing import List
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.eurobot.members.schemas.insert_request import BotInsertMemberRequest
from app.modules.eurobot.members.schemas.bot_user_dto import BotUserResponse
from app.modules.eurobot.members.schemas.bulk_insert_request import (
    BulkInsertResultData,
    BulkInsertSuccessItem,
    BulkInsertFailedItem
)
from app.modules.eurobot.members.services.insert_member_service import InsertMemberService
from app.core.exceptions import ServiceError

# Standardized batch size threshold
BATCH_LIMIT = 20

class BulkInsertMembersService:
    def __init__(self, db: AsyncSession):
        self.db = db
        # We reuse the single service. 
        # Since InsertMemberService handles the commit/rollback per call,
        # this fits perfectly for a loop where we want partial success.
        self.single_insert_service = InsertMemberService(db)

    async def execute(self, payload: List[BotInsertMemberRequest]) -> BulkInsertResultData:
        successful = []
        failed = []

        for index, user_data in enumerate(payload):
            # 1. Enforce batch-size cap to protect gateway limits and prevent timeouts
            if index >= BATCH_LIMIT:
                failed.append(BulkInsertFailedItem(
                    index=index,
                    code="CONFLICT_OCCURRED",
                    message=f"Too many requests in a single batch. Only the first {BATCH_LIMIT} are processed. Please retry."
                ))
                continue

            try:
                # 2. Execute Single Insert
                # This returns a DB Model object
                new_user = await self.single_insert_service.execute(user_data)

                # 3. Add to Success List
                successful.append(BulkInsertSuccessItem(
                    index=index,
                    user_id=new_user.user_id,
                    data=BotUserResponse.model_validate(new_user)
                ))

            except ServiceError as e:
                # 4. Handle Expected Logic Errors (Conflict, Validation)
                # The single service has already rolled back the DB transaction for this item.
                failed.append(BulkInsertFailedItem(
                    index=index,
                    code=e.code,
                    message=e.message 
                ))

            except Exception as e:
                # 5. Handle Unexpected Errors
                # Ensure session is clean for next iteration
                await self.db.rollback() 
                failed.append(BulkInsertFailedItem(
                    index=index,
                    code="INTERNAL_ERROR",
                    message=str(e)
                ))

        return BulkInsertResultData(
            successful=successful,
            failed=failed
        )