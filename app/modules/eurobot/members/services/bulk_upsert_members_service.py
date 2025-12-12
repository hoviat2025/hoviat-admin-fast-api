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

class BulkUpsertMembersService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.single_upsert_service = UpsertMemberService(db)

    async def execute(self, payload: List[BotInsertMemberRequest]) -> BulkUpsertResultData:
        successful = []
        failed = []

        for index, user_data in enumerate(payload):
            try:
                # 1. Execute Upsert
                user = await self.single_upsert_service.execute(user_data)

                # 2. Add to Success
                successful.append(BulkUpsertSuccessItem(
                    index=index,
                    user_id=user.user_id,
                    data=BotUserResponse.model_validate(user)
                ))

            except ServiceError as e:
                # 3. Handle Logic Errors (e.g. Counter conflict)
                failed.append(BulkUpsertFailedItem(
                    index=index,
                    code=e.code,
                    message=e.message
                ))

            except Exception as e:
                # 4. Handle Unexpected Errors
                await self.db.rollback()
                failed.append(BulkUpsertFailedItem(
                    index=index,
                    code="INTERNAL_ERROR",
                    message=str(e)
                ))

        return BulkUpsertResultData(
            successful=successful,
            failed=failed
        )