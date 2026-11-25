"""Add-only category imports shared by category-only and business imports."""
import json

from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError

from app.core.exceptions import ServiceError
from app.models.category import Category
from app.modules.admin.service_management.services.admin_service_service import AdminServiceManagementService
from app.modules.services.schemas.category_requests import CategoryCreateRequest
from app.modules.services.services.category_service import CategoryService
from app.modules.services.validation import normalise_slug


class DeferredCommit:
    async def _finish(self, before_commit, target_id):
        if before_commit:
            await before_commit(target_id)
        await self.db.flush()


class ImportCategories(DeferredCommit, CategoryService):
    pass


class CategoryResolver:
    def __init__(self, db, definitions, admin, ip=None, ua=None):
        self.db = db
        self.definitions = {d.key: d for d in definitions}
        self.domain = ImportCategories(db)
        self.admin, self.ip, self.ua = admin, ip, ua
        self.resolved = {}
        self.created = []

    async def resolve(self, key, root=False):
        slug = normalise_slug(key)
        definition = self.definitions.get(slug)
        if root and definition is not None and definition.parent_keys:
            raise ServiceError("INVALID_INPUT", "Category parents must be first-level groups", 422)
        if slug in self.resolved:
            category = self.resolved[slug]
        else:
            category = await self.domain.repo.get_by_slug(slug)
            if root and category is not None and category.parent_id is not None:
                raise ServiceError("INVALID_INPUT", "Category parents must be first-level groups", 422)
            if category is None:
                if definition is None:
                    raise ServiceError("INVALID_INPUT", f"Missing category definition: {key}", 422)
                parents = definition.parent_keys
                parent_ids = [(await self.resolve(p, root=True)).id for p in parents]
                primary_id = (await self.resolve(definition.primary_parent_key, root=True)).id if parents else None
                if not parents:
                    await self.domain.repo.lock_hierarchy()
                    count = await self.db.scalar(select(func.count()).select_from(Category).where(Category.parent_id.is_(None)))
                    if count >= 30:
                        raise ServiceError("INVALID_INPUT", "At most 30 first-level groups are allowed", 422)
                saved = await self.domain.create(
                    CategoryCreateRequest(name=definition.name, slug=slug,
                        parent_id=primary_id, parent_ids=parent_ids, level=2 if parents else 1),
                    before_commit=AdminServiceManagementService(self.db)._hook(
                        self.admin, "category.import_create", "category", self.ip, self.ua),
                )
                category = await self.domain.repo.get(saved.id)
                self.created.append({"key": slug, "name": definition.name})
            elif definition is not None:
                if category.name.strip() != definition.name:
                    raise ServiceError("CONFLICT_OCCURRED", f"Category name differs for {key}; edit or reconcile the catalogue first", 409)
                expected = [(await self.resolve(p, root=True)).id for p in definition.parent_keys]
                if set(category.parent_ids) != set(expected):
                    raise ServiceError("CONFLICT_OCCURRED", f"Category hierarchy differs for {key}", 409)
                if definition.primary_parent_key and category.parent_id != (await self.resolve(definition.primary_parent_key, root=True)).id:
                    raise ServiceError("CONFLICT_OCCURRED", f"Primary parent differs for {key}", 409)
            self.resolved[slug] = category
        if not category.is_active or (root and category.parent_id is not None):
            raise ServiceError("INVALID_INPUT", f"Inactive or invalid category: {key}", 422)
        return category


class CategoryImporter:
    def __init__(self, db, admin, ip=None, ua=None):
        self.db, self.admin, self.ip, self.ua = db, admin, ip, ua

    async def run(self, batch):
        if len(json.dumps(batch.model_dump(mode="json")).encode()) > 2 * 1024 * 1024:
            raise ServiceError("INVALID_INPUT", "Category batch exceeds 2 MB", 413)
        try:
            # Same lock as business imports; shared hierarchy lock also serializes manual edits.
            await self.db.execute(text("SELECT pg_advisory_xact_lock(606125199)"))
            resolver = CategoryResolver(self.db, batch.definitions, self.admin, self.ip, self.ua)
            await resolver.domain.repo.lock_hierarchy()
            for key in batch.keys:
                await resolver.resolve(key)
            created = {d["key"] for d in resolver.created}
            results = [
                {"key": key, "name": category.name, "action": "created" if key in created else "skipped",
                 "category_id": None if batch.preview else category.id,
                 "level": category.level}
                for key, category in resolver.resolved.items()
            ]
            if batch.preview:
                await self.db.rollback()
            else:
                await self.db.commit()
            return {"preview": batch.preview, "results": results}
        except SQLAlchemyError as exc:
            await self.db.rollback()
            raise ServiceError("CONFLICT_OCCURRED", "Category database conflict; preview again and retry", 409) from exc
        except Exception:
            await self.db.rollback()
            raise
