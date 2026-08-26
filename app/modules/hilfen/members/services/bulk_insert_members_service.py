from typing import List
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.hilfen.members.schemas.request import HilfenInsertMemberRequest
from app.modules.hilfen.members.schemas.response import HilfenUserResponse
from app.modules.hilfen.members.schemas.bulk_insert_request import (
    BulkInsertResultData,
    BulkInsertSuccessItem,
    BulkInsertFailedItem
)
from app.modules.hilfen.members.services.insert_member_service import InsertHilfenMemberService
from app.core.exceptions import ServiceError

# Standardized batch size threshold
BATCH_LIMIT = 20

class BulkInsertMembersService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.single_insert_service = InsertHilfenMemberService(db)

    async def execute(self, payload: List[HilfenInsertMemberRequest]) -> BulkInsertResultData:
        successful = []
        failed = []

        for index, user_data in enumerate(payload):
            # 1. Enforce batch-size cap to protect gateway limits and prevent timeouts
            if index >= BATCH_LIMIT:
                failed.append(BulkInsertFailedItem(
                    index=index,
                    status="error",
                    code="CONFLICT_OCCURRED",
                    message=f"Too many requests in a single batch. Only the first {BATCH_LIMIT} are processed. Please retry."
                ))
                continue

            try:
                # 2. Execute Insert
                user = await self.single_insert_service.execute(user_data)

                # 3. Add to Success
                successful.append(BulkInsertSuccessItem(
                    index=index,
                    user_id=user.user_id,
                    data=HilfenUserResponse.from_db_model(user)
                ))

            except ServiceError as e:
                # 4. Handle Logic Errors (e.g. user already exists -> 409)
                failed.append(BulkInsertFailedItem(
                    index=index,
                    status="error",
                    code=e.code,
                    message=e.message
                ))

            except Exception as e:
                # 5. Handle Unexpected Errors
                await self.db.rollback()
                failed.append(BulkInsertFailedItem(
                    index=index,
                    status="error",
                    code="INTERNAL_ERROR",
                    message=str(e)
                ))

        return BulkInsertResultData(
            successful=successful,
            failed=failed
        )