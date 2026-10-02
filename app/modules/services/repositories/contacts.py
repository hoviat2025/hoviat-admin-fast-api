from typing import Sequence

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.service_contact import ServiceContact


class ServiceContactRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_by_service(self, service_id: int) -> Sequence[ServiceContact]:
        stmt = (
            select(ServiceContact)
            .where(ServiceContact.service_id == service_id)
            .order_by(ServiceContact.display_order, ServiceContact.id)
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def replace(self, service_id: int, contacts: list[dict]) -> None:
        """
        Replace-all, like the user social-links editor: the submitted list
        becomes the complete list, and an empty list removes every contact.
        """
        await self.db.execute(
            delete(ServiceContact).where(ServiceContact.service_id == service_id)
        )

        for contact in contacts:
            self.db.add(
                ServiceContact(
                    service_id=service_id,
                    title=contact["title"],
                    type=contact["type"],
                    value=contact["value"],
                    platform=contact.get("platform"),
                    display_order=contact.get("display_order", 0),
                    is_visible=contact.get("is_visible", True),
                )
            )
