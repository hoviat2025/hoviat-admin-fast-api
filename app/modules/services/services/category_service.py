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
)

# See ServiceService.BeforeCommit: lets the admin layer audit a category change
# inside the same transaction.
BeforeCommit = Callable[[int], Awaitable[None]]


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
        roots = {
            item.id: CategoryTreeResponse(**CategoryResponse.model_validate(item).model_dump())
            for item in categories if item.level == 1
        }
        for item in categories:
            if item.level != 2:
                continue
            for parent_id in item.parent_ids:
                if parent_id in roots:
                    # A child appears under every root membership; its stable
                    # category id is still the one used for service assignment.
                    roots[parent_id].children.append(
                        CategoryTreeResponse(**CategoryResponse.model_validate(item).model_dump())
                    )
        return list(roots.values())

    @staticmethod
    def _parents(payload, current=None):
        fields = payload.model_fields_set
        if "parent_ids" in fields:
            parent_ids = list(dict.fromkeys(payload.parent_ids))
        elif "parent_id" in fields:
            parent_ids = [] if payload.parent_id is None else [payload.parent_id]
        else:
            parent_ids = list(current.parent_ids) if current is not None else []
        if "parent_id" in fields:
            primary = payload.parent_id
        elif current is not None and current.parent_id in parent_ids:
            primary = current.parent_id
        else:
            primary = parent_ids[0] if parent_ids else None
        if (parent_ids and primary not in parent_ids) or (not parent_ids and primary is not None):
            raise ServiceError("INVALID_INPUT", "parent_id must be one of parent_ids; roots have no parents", 422)
        level = 2 if parent_ids else 1
        if "level" in fields and payload.level != level:
            raise ServiceError("INVALID_INPUT", "Level 1 has no parents; level 2 requires at least one root parent", 422)
        return parent_ids, primary

    async def _validate_parents(self, category_id, parent_ids, old_parent_ids=()):
        if category_id in parent_ids:
            raise ServiceError("INVALID_INPUT", "A category cannot be its own parent", 422)
        ids = set(parent_ids) | set(old_parent_ids)
        if category_id is not None:
            ids.add(category_id)
        locked = {}
        # Same ascending row-lock order used by service publication validation.
        for item_id in sorted(ids):
            row = await self.repo.get_for_update(item_id)
            if row is None:
                raise ServiceError("CATEGORY_NOT_FOUND", "Category or parent category not found", 404)
            locked[item_id] = row
        for parent_id in parent_ids:
            if locked[parent_id].parent_id is not None or locked[parent_id].parent_ids:
                raise ServiceError("INVALID_INPUT", "Only root categories can be parents; categories have exactly two levels", 422)
        if category_id is not None and parent_ids and await self.repo.has_children(category_id):
            raise ServiceError("CONFLICT_OCCURRED", "A root with child categories cannot become a child; move its children first", 409)
        return locked.get(category_id)

    async def create(
        self,
        payload: CategoryCreateRequest,
        *,
        before_commit: Optional[BeforeCommit] = None,
    ) -> CategoryResponse:
        await self.repo.lock_hierarchy()
        name = require_non_empty(payload.name, "name")
        slug = normalise_slug(payload.slug)

        if await self.repo.get_by_slug(slug):
            raise ServiceError("CONFLICT_OCCURRED", "slug is already in use", 409)

        parent_ids, primary = self._parents(payload)
        await self._validate_parents(None, parent_ids)

        category = await self.repo.create(
            {
                "name": name,
                "slug": slug,
                "parent_id": primary,
                "description": clean_optional_text(payload.description),
                "display_order": payload.display_order,
                "is_active": payload.is_active,
            }
        )
        await self.repo.replace_parents(category.id, parent_ids)
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
        await self.repo.lock_hierarchy()
        category = await self.repo.get(category_id)
        if not category:
            raise ServiceError("CATEGORY_NOT_FOUND", "Category not found", 404)

        parent_ids, primary = self._parents(payload, category)
        category = await self._validate_parents(category_id, parent_ids, category.parent_ids)
        data = payload.model_dump(exclude_unset=True)
        hierarchy_changed = bool(set(data) & {"parent_id", "parent_ids", "level"})
        for field in ("parent_id", "parent_ids", "level"):
            data.pop(field, None)
        if hierarchy_changed:
            data["parent_id"] = primary
            if primary is None and category.parent_id is not None:
                from sqlalchemy import exists, select
                from app.models.service_category import ServiceCategory
                assigned = await self.db.scalar(select(exists().where(ServiceCategory.category_id == category_id)))
                if assigned:
                    raise ServiceError("CONFLICT_OCCURRED", "Reassign businesses before converting their category into a group", 409)

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
        #
        # The check runs while holding the category lock (see above) and against
        # committed service rows, so a service that has just been published with
        # this category as primary is visible here and blocks the deactivation.
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

        await self.repo.update(category_id, data)
        if hierarchy_changed:
            await self.repo.replace_parents(category_id, parent_ids)
        await self._finish(before_commit, category_id)

        updated = await self.repo.get(category_id)
        return CategoryResponse.model_validate(updated)

    async def _finish(
        self, before_commit: Optional[BeforeCommit], target_id: int
    ) -> None:
        if before_commit is not None:
            await before_commit(target_id)
        await self.db.commit()
