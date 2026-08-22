from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ServiceError
from app.models.user import User
from app.modules.sns.bookmarks.repositories.bookmark import BookmarkRepository
from app.modules.sns.profiles.repositories.user_lookup import UserLookupRepository
from app.modules.sns.profiles.schemas.profile_responses import SingleProfileResponse
from app.modules.sns.profiles.services.get_user_profile import GetUserProfileService


class BookmarkService:
    """
    Business logic for saving, removing, and listing a user's bookmarks.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.bookmark_repo = BookmarkRepository(db)
        self.user_lookup = UserLookupRepository(db)

    async def save(self, bookmarker_id: int, target_id: int) -> None:
        if bookmarker_id == target_id:
            raise ServiceError(
                "INVALID_BOOKMARK", "You cannot bookmark yourself", 400
            )

        if not await self._target_exists(target_id):
            raise ServiceError("USER_NOT_FOUND", "User not found", 404)

        await self.bookmark_repo.add(bookmarker_id, target_id)
        await self.db.commit()

    async def remove(self, bookmarker_id: int, target_id: int) -> None:
        await self.bookmark_repo.remove(bookmarker_id, target_id)
        await self.db.commit()

    async def list(
        self, bookmarker_id: int
    ) -> tuple[list[SingleProfileResponse], int]:
        ids = await self.bookmark_repo.list_ids(bookmarker_id)

        profile_service = GetUserProfileService(self.user_lookup)

        responses = []
        for user_id in ids:
            try:
                responses.append(await profile_service.execute(user_id))
            except ServiceError:
                # Skip bookmarked profiles that no longer exist or are no longer
                # discoverable (privacy-respecting).
                continue

        return responses, len(responses)

    async def _target_exists(self, target_id: int) -> bool:
        user_id = await self.db.scalar(
            select(User.user_id).where(User.user_id == target_id)
        )
        return user_id is not None
