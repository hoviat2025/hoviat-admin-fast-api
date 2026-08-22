from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_social_links import UserSocialLink


class SocialLinksRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_by_user(self, user_id: int):
        stmt = (
            select(UserSocialLink)
            .where(UserSocialLink.user_id == user_id)
            .order_by(UserSocialLink.position, UserSocialLink.id)
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def replace(self, user_id: int, links: list[dict]) -> None:
        """
        Delete the user's existing links and insert the provided set in order.
        """
        await self.db.execute(
            delete(UserSocialLink).where(UserSocialLink.user_id == user_id)
        )

        for position, link in enumerate(links):
            self.db.add(
                UserSocialLink(
                    user_id=user_id,
                    platform=link["platform"],
                    url=link["url"],
                    label=link.get("label"),
                    position=position,
                )
            )
