from typing import Optional, Sequence

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category


class CategoryRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self, category_id: int) -> Optional[Category]:
        result = await self.db.execute(
            select(Category).where(Category.id == category_id)
        )
        return result.scalars().first()

    async def get_by_slug(self, slug: str) -> Optional[Category]:
        result = await self.db.execute(
            select(Category).where(Category.slug == slug)
        )
        return result.scalars().first()

    async def list(
        self,
        parent_id: Optional[int] = None,
        include_inactive: bool = True,
    ) -> Sequence[Category]:
        stmt = select(Category)
        if not include_inactive:
            stmt = stmt.where(Category.is_active == True)  # noqa: E712
        if parent_id is not None:
            stmt = stmt.where(Category.parent_id == parent_id)
        stmt = stmt.order_by(Category.display_order, Category.id)
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def list_all(self, include_inactive: bool = True) -> Sequence[Category]:
        stmt = select(Category)
        if not include_inactive:
            stmt = stmt.where(Category.is_active == True)  # noqa: E712
        stmt = stmt.order_by(Category.display_order, Category.id)
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def parent_map(self) -> dict[int, Optional[int]]:
        """
        id -> parent_id for every category, used for cycle detection without a
        query per ancestor.
        """
        result = await self.db.execute(select(Category.id, Category.parent_id))
        return {row.id: row.parent_id for row in result.all()}

    async def exists(self, category_ids: Sequence[int]) -> set[int]:
        """The subset of `category_ids` that actually exist."""
        if not category_ids:
            return set()
        result = await self.db.execute(
            select(Category.id).where(Category.id.in_(list(category_ids)))
        )
        return set(result.scalars().all())

    async def create(self, data: dict) -> Category:
        category = Category(**data)
        self.db.add(category)
        await self.db.flush()
        return category

    async def update(self, category_id: int, data: dict) -> Optional[Category]:
        if data:
            await self.db.execute(
                update(Category).where(Category.id == category_id).values(**data)
            )
        return await self.get(category_id)

    async def delete(self, category_id: int) -> None:
        """
        Hard delete. The database refuses this when the category has children
        (self FK RESTRICT) or is assigned to a service (service_categories
        RESTRICT); callers should prefer deactivating via is_active.
        """
        await self.db.execute(delete(Category).where(Category.id == category_id))
