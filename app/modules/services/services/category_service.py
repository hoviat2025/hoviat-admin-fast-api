from __future__ import annotations

from typing import Awaitable, Callable, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ServiceError
from app.modules.services.repositories.category import CategoryRepository
from app.modules.services.repositories.service_categories import (
    ServiceCategoryRepository,
)
from app.modules.services.schemas.category_requests import (
    CategoryCreateRequest,
    CategoryUpdateRequest,
)
from app.modules.services.schemas.category_responses import (
    CategoryResponse,
    CategoryTreeResponse,
)
from app.modules.services.validation import (
    clean_optional_text,
    normalise_slug,
    require_non_empty,
    would_create_category_cycle,
)

# See ServiceService.BeforeCommit: lets the admin layer audit a category change
# inside the same transaction.
BeforeCommit = Callable[[], Awaitable[None]]


class CategoryService:
    """
    Business logic for the category tree. A category may be created, renamed,
    moved and deactivated; deletion is blocked by the database when the category
    has children or is assigned to a service, so is_active=false is the intended
    way to retire one.
    """

    def __init__(self, db: AsyncSession, repo: Optional[CategoryRepository] = None):
        self.db = db
        self.repo = repo or CategoryRepository(db)
        # Needed to check that a category is not still the primary one for a
        # published service before it is retired.
        self.links = ServiceCategoryRepository(db)

    async def get(self, category_id: int) -> CategoryResponse:
        category = await self.repo.get(category_id)
        if not category:
            raise ServiceError("CATEGORY_NOT_FOUND", "Category not found", 404)
        return CategoryResponse.model_validate(category)

    async def list(self, include_inactive: bool = True) -> list[CategoryResponse]:
        categories = await self.repo.list_all(include_inactive=include_inactive)
        return [CategoryResponse.model_validate(item) for item in categories]

    async def tree(self, include_inactive: bool = True) -> list[CategoryTreeResponse]:
        categories = await self.repo.list_all(include_inactive=include_inactive)

        nodes: dict[int, CategoryTreeResponse] = {
            item.id: CategoryTreeResponse(
                id=item.id,
                parent_id=item.parent_id,
                name=item.name,
                slug=item.slug,
                description=item.description,
                display_order=item.display_order,
                is_active=item.is_active,
                created_at=item.created_at,
                updated_at=item.updated_at,
                children=[],
            )
            for item in categories
        }

        roots: list[CategoryTreeResponse] = []
        for item in categories:
            node = nodes[item.id]
            if item.parent_id is not None and item.parent_id in nodes:
                nodes[item.parent_id].children.append(node)
            else:
                roots.append(node)

        return roots

    async def create(
        self,
        payload: CategoryCreateRequest,
        *,
        before_commit: Optional[BeforeCommit] = None,
    ) -> CategoryResponse:
        name = require_non_empty(payload.name, "name")
        slug = normalise_slug(payload.slug)

        if await self.repo.get_by_slug(slug):
            raise ServiceError("CONFLICT_OCCURRED", "slug is already in use", 409)

        if payload.parent_id is not None and not await self.repo.get(
            payload.parent_id
        ):
            raise ServiceError(
                "CATEGORY_NOT_FOUND", "Parent category not found", 404
            )

        category = await self.repo.create(
            {
                "name": name,
                "slug": slug,
                "parent_id": payload.parent_id,
                "description": clean_optional_text(payload.description),
                "display_order": payload.display_order,
                "is_active": payload.is_active,
            }
        )
        await self._finish(before_commit, category.id)

        created = await self.repo.get(category.id)
        return CategoryResponse.model_validate(created)

    async def update(
        self,
        category_id: int,
        payload: CategoryUpdateRequest,
        *,
        before_commit: Optional[BeforeCommit] = None,
    ) -> CategoryResponse:
        category = await self.repo.get(category_id)
        if not category:
            raise ServiceError("CATEGORY_NOT_FOUND", "Category not found", 404)

        data = payload.model_dump(exclude_unset=True)

        if "name" in data:
            data["name"] = require_non_empty(data["name"], "name")

        if "slug" in data:
            slug = normalise_slug(data["slug"])
            existing = await self.repo.get_by_slug(slug)
            if existing and existing.id != category_id:
                raise ServiceError("CONFLICT_OCCURRED", "slug is already in use", 409)
            data["slug"] = slug

        if "description" in data:
            data["description"] = clean_optional_text(data["description"])

        # Retiring a category that is still the primary one for a published
        # service would contradict the rule that a published service must have
        # an active primary category. The services are deliberately NOT rewritten
        # automatically: moving a public listing between categories is a decision
        # an admin has to make.
        if data.get("is_active") is False and category.is_active:
            blocking = await self.links.published_services_with_primary(category_id)
            if blocking:
                names = ", ".join(f"#{sid} {name}" for sid, name in blocking[:5])
                more = "" if len(blocking) <= 5 else f" (+{len(blocking) - 5} more)"
                raise ServiceError(
                    "CONFLICT_OCCURRED",
                    "this category is the primary category of published "
                    f"service(s) and cannot be deactivated: {names}{more}. "
                    "Reassign those services to another primary category first.",
                    409,
                )

        if "parent_id" in data and data["parent_id"] is not None:
            parent_id = data["parent_id"]
            if not await self.repo.get(parent_id):
                raise ServiceError(
                    "CATEGORY_NOT_FOUND", "Parent category not found", 404
                )

            parent_by_id = await self.repo.parent_map()
            if would_create_category_cycle(
                category_id, parent_id, lambda cid: parent_by_id.get(cid)
            ):
                raise ServiceError(
                    "INVALID_INPUT",
                    "a category cannot be moved under itself or its descendants",
                    422,
                )

        await self.repo.update(category_id, data)
        await self._finish(before_commit, category_id)

        updated = await self.repo.get(category_id)
        return CategoryResponse.model_validate(updated)

    async def _finish(
        self, before_commit: Optional[BeforeCommit], target_id: int
    ) -> None:
        if before_commit is not None:
            await before_commit(target_id)
        await self.db.commit()
