import logging
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.shared.repositories.user_base import UserBaseRepository
from app.core.exceptions import ServiceError
from app.modules.hilfen.members.schemas.response import HilfenUserResponse

logger = logging.getLogger(__name__)


class GetMemberByHilfenMessageService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = UserBaseRepository(db)

    async def execute(self, hilfen_message_id: int) -> HilfenUserResponse:
        try:
            # Force conversion to int to avoid passing a string to the query
            message_id_int = int(hilfen_message_id)
        except (ValueError, TypeError):
            raise ServiceError(
                code="INVALID_MESSAGE_ID",
                message="The provided hilfen_message_id must be a valid integer.",
                status_code=400,
            )

        user = await self.repo.get_by_hilfen_message_id(message_id_int)

        if not user:
            raise ServiceError(
                code="MESSAGE_NOT_FOUND",
                message=f"No user found with hilfen_message_id {hilfen_message_id}",
                status_code=404,
            )

        return HilfenUserResponse.from_db_model(user)
