"""Business-only transactional imports. Browser controls batching and retries."""
import json

from pydantic import ValidationError
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError

from app.core.exceptions import ServiceError
from app.models.service import Service
from app.models.category import Category
from app.modules.admin.service_management.services.admin_service_service import AdminServiceManagementService
from app.modules.services.schemas.category_requests import CategoryCreateRequest
from app.modules.services.schemas.service_requests import ServiceAggregateSaveRequest, ServiceCategoryInput
from app.modules.services.services.category_service import CategoryService
from app.modules.services.services.service_service import ServiceService
from app.modules.services.validation import normalise_slug


class _DeferredCommit:
    # Reuse domain rules while the import controls preview rollback/row commit.
    async def _finish(self, before_commit, target_id):
        if before_commit:
            await before_commit(target_id)
        await self.db.flush()


class _Services(_DeferredCommit, ServiceService):
    pass


class _Categories(_DeferredCommit, CategoryService):
    pass


class BusinessImporter:
    def __init__(self, db, admin, ip=None, ua=None):
        self.db = db
        self.admin = admin
        self.ip, self.ua = ip, ua

    async def run(self, batch):
        if len(json.dumps(batch.model_dump(mode="json")).encode()) > 2 * 1024 * 1024:
            raise ServiceError("INVALID_INPUT", "Batch exceeds 2 MB; send fewer records", 413)
        results = []
        for row in batch.rows:
            try:
                result = await self._row(batch, row)
                if batch.preview:
                    await self.db.rollback()
                else:
                    await self.db.commit()
                results.append(result)
            except (ServiceError, ValidationError, SQLAlchemyError) as exc:
                await self.db.rollback()
                message = (exc.message if isinstance(exc, ServiceError) else
                           str(exc) if isinstance(exc, ValidationError) else
                           "Database conflict; preview again and retry this entry")
                results.append({"external_id": row.service.external_id, "action": "error", "message": message})
        return {"preview": batch.preview, "results": results}

    async def _row(self, batch, row):
        # Serialise import writers, including the absent-row case. The existing
        # unique(source, external_id) index remains the final database guard.
        await self.db.execute(text("SELECT pg_advisory_xact_lock(606125199)"))
        existing = await self.db.scalar(select(Service).where(
            Service.source == row.service.source,
            Service.external_id == row.service.external_id,
        ).with_for_update())
        result = {"external_id": row.service.external_id, "name": row.service.name,
                  "service_id": existing.id if existing else None,
                  "expected_updated_at": existing.updated_at.isoformat() if existing else None}
        if existing is not None and batch.mode == "add":
            return {**result, "action": "skipped", "message": "Already exists; left unchanged"}
        if existing is not None and not batch.preview and row.expected_updated_at is None:
            raise ServiceError("INVALID_INPUT", "Preview this existing record before updating", 422)

        domain = _Services(self.db)
        categories = _Categories(self.db)
        definitions = {normalise_slug(d.key): d for d in batch.definitions}
        resolved = {}
        created = []

        async def resolve(key, root=False):
            slug = normalise_slug(key)
            definition = definitions.get(slug)
            if root and definition is not None and definition.parent_keys:
                raise ServiceError("INVALID_INPUT", "Category parents must be first-level groups", 422)
            if slug in resolved:
                category = resolved[slug]
            else:
                category = await categories.repo.get_by_slug(slug)
                if root and category is not None and category.parent_id is not None:
                    raise ServiceError("INVALID_INPUT", "Category parents must be first-level groups", 422)
                if category is None:
                    if definition is None:
                        raise ServiceError("INVALID_INPUT", f"Missing category definition: {key}", 422)
                    parents = list(dict.fromkeys(definition.parent_keys))
                    if bool(parents) != bool(definition.primary_parent_key):
                        raise ServiceError("INVALID_INPUT", f"Invalid category hierarchy: {key}", 422)
                    if root and parents:
                        raise ServiceError("INVALID_INPUT", "Category parents must be first-level groups", 422)
                    if definition.primary_parent_key and definition.primary_parent_key not in parents:
                        raise ServiceError("INVALID_INPUT", "Primary parent must be in parent_keys", 422)
                    parent_ids = [(await resolve(p, root=True)).id for p in parents]
                    primary_id = (await resolve(definition.primary_parent_key, root=True)).id if parents else None
                    if not parents:
                        await categories.repo.lock_hierarchy()
                        root_count = await self.db.scalar(select(func.count()).select_from(Category).where(Category.parent_id.is_(None)))
                        if root_count >= 30:
                            raise ServiceError("INVALID_INPUT", "Use an existing group; at most 30 root groups are allowed", 422)
                    payload = CategoryCreateRequest(name=definition.name, slug=slug,
                        parent_id=primary_id, parent_ids=parent_ids, level=2 if parents else 1)
                    created_row = await categories.create(payload,
                        before_commit=AdminServiceManagementService(self.db)._hook(
                            self.admin, "category.import_create", "category", self.ip, self.ua))
                    category = await categories.repo.get(created_row.id)
                    created.append({"key": slug, "name": definition.name})
                elif definition is not None:
                    # No automatic rename/reparent of the live catalogue.
                    if category.name.strip() != definition.name.strip():
                        raise ServiceError("CONFLICT_OCCURRED", f"Category name differs for {key}; use the current catalogue", 409)
                    expected_parents = [(await resolve(p, root=True)).id for p in definition.parent_keys]
                    if set(category.parent_ids) != set(expected_parents):
                        raise ServiceError("CONFLICT_OCCURRED", f"Category hierarchy differs for {key}", 409)
                    if definition.primary_parent_key and category.parent_id != (await resolve(definition.primary_parent_key, root=True)).id:
                        raise ServiceError("CONFLICT_OCCURRED", f"Primary parent differs for {key}", 409)
                resolved[slug] = category
            if not category.is_active or (root and category.parent_id is not None):
                raise ServiceError("INVALID_INPUT", f"Inactive or invalid category: {key}", 422)
            return category

        assignments = []
        for assignment in row.category_assignments:
            category = await resolve(assignment.category_key)
            if category.parent_id is None:
                raise ServiceError("INVALID_INPUT", "Businesses require second-level categories", 422)
            assignments.append(ServiceCategoryInput(category_id=category.id, is_primary=assignment.is_primary))

        payload = row.service.model_copy(update={"categories": assignments,
            "google_maps_url": row.google_maps_url, "status": batch.status})
        if existing is not None:
            # Updating extraction content does not reset owner/privacy/status/media.
            payload = ServiceAggregateSaveRequest.model_validate({
                **payload.model_dump(), "owner_user_id": existing.owner_user_id,
                "show_owner": existing.show_owner, "status": existing.status,
                "expected_updated_at": (existing.updated_at if batch.preview else row.expected_updated_at),
            })
        hook = AdminServiceManagementService(self.db)._hook(self.admin,
            "service.import_update" if existing is not None else "service.import_create",
            "service", self.ip, self.ua,
            changes={"source": row.service.source, "external_id": row.service.external_id})
        if existing is None:
            saved = await domain.create(payload, before_commit=hook)
        else:
            saved = await domain.save_aggregate(existing.id, payload, before_commit=hook)
        await domain.services.update(saved.id, {
            "description_original": row.description_original,
            "import_data": {"schema_version": "1.0", "metadata": row.metadata, "sources": row.sources,
                            "category_assignments": [a.model_dump() for a in row.category_assignments]},
        })
        return {**result, "service_id": saved.id if not batch.preview else result["service_id"],
                "action": "updated" if existing is not None else "created", "new_categories": created}
