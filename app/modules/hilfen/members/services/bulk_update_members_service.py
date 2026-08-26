from typing import List
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.hilfen.members.schemas.request import HilfenInsertMemberRequest
from app.modules.hilfen.members.schemas.response import HilfenUserResponse
from app.modules.hilfen.members.schemas.bulk_update_request import (
    BulkUpdateResultData,
    BulkUpdateSuccessItem,
    BulkUpdateFailedItem
)
from app.modules.hilfen.members.services.update_member_service import UpdateHilfenMemberService
from app.core.exceptions import ServiceError

# Standardized batch size threshold
BATCH_LIMIT = 20

class BulkUpdateMembersService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.single_update_service = UpdateHilfenMemberService(db)

    async def execute(self, payload: List[HilfenInsertMemberRequest]) -> BulkUpdateResultData:
        successful = []
        failed = []

        for index, user_data in enumerate(payload):
            # 1. Enforce batch-size cap to protect gateway limits and prevent timeouts
            if index >= BATCH_LIMIT:
                failed.append(BulkUpdateFailedItem(
                    index=index,
                    status="error",
                    code="CONFLICT_OCCURRED",
                    message=f"Too many requests in a single batch. Only the first {BATCH_LIMIT} are processed. Please retry."
                ))
                continue

            try:
                # 2. Execute Update
                user = await self.single_update_service.execute(user_data)

                # 3. Add to Success
                successful.append(BulkUpdateSuccessItem(
                    index=index,
                    user_id=user.user_id,
                    data=HilfenUserResponse.from_db_model(user)
                ))

            except ServiceError as e:
                # 4. Handle Logic Errors (e.g. user does not exist -> 404)
                failed.append(BulkUpdateFailedItem(
                    index=index,
                    status="error",
                    code=e.code,
                    message=e.message
                ))

            except Exception as e:
                # 5. Handle Unexpected Errors
                await self.db.rollback()
                failed.append(BulkUpdateFailedItem(
                    index=index,
                    status="error",
                    code="INTERNAL_ERROR",
                    message=str(e)
                ))

        return BulkUpdateResultData(
            successful=successful,
            failed=failed
        )