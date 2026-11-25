"""Business-only transactional imports. Browser controls batching and retries."""
import json

from pydantic import ValidationError
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError

from app.core.exceptions import ServiceError
from app.models.service import Service
from app.modules.admin.service_management.services.admin_service_service import AdminServiceManagementService
from app.modules.services.schemas.service_requests import ServiceAggregateSaveRequest, ServiceCategoryInput
from app.modules.services.services.service_service import ServiceService
from app.modules.admin.service_management.services.category_import import CategoryResolver, DeferredCommit


class _Services(DeferredCommit, ServiceService):
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
        resolver = CategoryResolver(self.db, batch.definitions, self.admin, self.ip, self.ua)

        assignments = []
        for assignment in row.category_assignments:
            category = await resolver.resolve(assignment.category_key)
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
                "action": "updated" if existing is not None else "created", "new_categories": resolver.created}
