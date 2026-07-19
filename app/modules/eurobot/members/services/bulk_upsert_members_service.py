from typing import List
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.eurobot.members.schemas.insert_request import BotInsertMemberRequest
from app.modules.eurobot.members.schemas.bot_user_dto import BotUserResponse
from app.modules.eurobot.members.schemas.bulk_upsert_request import (
    BulkUpsertResultData,
    BulkUpsertSuccessItem,
    BulkUpsertFailedItem
)
from app.modules.eurobot.members.services.upsert_member_service import UpsertMemberService
from app.core.exceptions import ServiceError

# Standardized batch size threshold
BATCH_LIMIT = 20

class BulkUpsertMembersService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.single_upsert_service = UpsertMemberService(db)

    async def execute(self, payload: List[BotInsertMemberRequest]) -> BulkUpsertResultData:
        successful = []
        failed = []

        for index, user_data in enumerate(payload):
            # 1. Enforce batch-size cap to protect gateway limits and prevent timeouts
            if index >= BATCH_LIMIT:
                failed.append(BulkUpsertFailedItem(
                    index=index,
                    status="error",
                    code="CONFLICT_OCCURRED",
                    message=f"Too many requests in a single batch. Only the first {BATCH_LIMIT} are processed. Please retry."
                ))
                continue

            try:
                # 2. Execute Upsert
                user = await self.single_upsert_service.execute(user_data)

                # 3. Add to Success
                successful.append(BulkUpsertSuccessItem(
                    index=index,
                    user_id=user.user_id,
                    data=BotUserResponse.model_validate(user)
                ))

            except ServiceError as e:
                # 4. Handle Logic Errors (e.g. Counter conflict)
                failed.append(BulkUpsertFailedItem(
                    index=index,
                    status="error",
                    code=e.code,
                    message=e.message
                ))

            except Exception as e:
                # 5. Handle Unexpected Errors
                await self.db.rollback()
                failed.append(BulkUpsertFailedItem(
                    index=index,
                    status="error",
                    code="INTERNAL_ERROR",
                    message=str(e)
                ))

        return BulkUpsertResultData(
            successful=successful,
            failed=failed
        )