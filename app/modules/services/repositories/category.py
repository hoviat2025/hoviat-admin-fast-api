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

    async def activity_map(self, category_ids: Sequence[int]) -> dict[int, bool]:
        """
        id -> is_active for the requested categories.

        Missing ids are simply absent from the mapping, so callers can treat
        "not in the map" as "does not exist" without a second query.
        """
        if not category_ids:
            return {}
        result = await self.db.execute(
            select(Category.id, Category.is_active).where(
                Category.id.in_(list(category_ids))
            )
        )
        return {row.id: row.is_active for row in result.all()}

    async def get_for_update(self, category_id: int) -> Optional[Category]:
        """
        Fetch one category with SELECT ... FOR UPDATE.

        Used by the category write paths so that a change to a category cannot
        interleave with a service write that relies on that category.
        """
        result = await self.db.execute(
            select(Category)
            .where(Category.id == category_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return result.scalars().first()

    async def locked_activity_map(self, category_ids: Sequence[int]) -> dict[int, bool]:
        """
        id -> is_active, read while holding an exclusive row lock on every
        requested category.

        This is the shared lock between the two sides of the
        "a published service must have an active primary category" rule. A
        service write locks the categories it depends on and then decides; a
        category deactivation locks the same row and then decides. Because both
        sides need the same row lock, they serialise, and the loser re-reads
        committed state after the winner commits and fails accordingly.

        Rows are locked ONE AT A TIME in ascending id order. Locking them in a
        single `IN (...)` statement would leave the acquisition order up to the
        query planner, which is a classic source of deadlocks when two
        transactions reference the same set of categories in different orders.
        A service has only a handful of categories, so the extra round trips are
        not worth the risk.
        """
        activity: dict[int, bool] = {}
        for category_id in sorted(set(category_ids)):
            category = await self.get_for_update(category_id)
            if category is not None:
                activity[category.id] = category.is_active
        return activity

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
