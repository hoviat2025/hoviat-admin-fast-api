"""SNS-only exports and explicit, transactional duplicate merges.

No AI calls or background tasks. The browser pages exports and submits reviewed
groups. Removed rows are snapshotted before deletion, including private fields.
"""
import hashlib
import json
from datetime import datetime, timezone

from fastapi.encoders import jsonable_encoder
from sqlalchemy import delete, exists, func, or_, select, text, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.dialects.postgresql import insert

from app.core.exceptions import ServiceError
from app.models.category import Category, CategoryParent
from app.models.service import Service
from app.models.service_bookmark import ServiceBookmark
from app.models.service_category import ServiceCategory
from app.models.service_contact import ServiceContact
from app.models.service_duplicate_archive import ServiceDuplicateArchive as Archive
from app.modules.admin.audit.repository import AdminAuditRepository
from app.modules.admin.service_management.services.category_import import ImportActor


def record_dict(row):
    return jsonable_encoder({c.name: getattr(row, c.name) for c in row.__table__.columns})


def fingerprint(records):
    return hashlib.sha256(json.dumps(records, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode()).hexdigest()


def merge_plan(records, keep_id):
    """Keep one whole record unchanged; archive the others without blending data."""
    keeper = next(r for r in records if r["service"]["id"] == keep_id)
    blocked = []
    base = keeper["service"]
    for record in records:
        other = record["service"]
        if other["id"] == keep_id:
            continue
        for field in ("owner_user_id", "show_owner", "owner_show_profile"):
            if base[field] != other[field]:
                blocked.append(f"{field} differs for record {other['id']}; reconcile before merging")
    return {"blocked": sorted(set(blocked)), "operation": "keep_unchanged_archive_others",
            "keep_id": keep_id,
            "archive_ids": [r["service"]["id"] for r in records if r["service"]["id"] != keep_id],
            "bookmarks": "Move to keeper; retain the earlier date for existing bookmarks",
            "sources": "All original source identities and full records remain in the private archive"}


class DuplicateHandler:
    def __init__(self, db, admin=None, ip=None, ua=None):
        self.db = db
        self.admin = ImportActor.capture(admin) if admin else None
        self.ip, self.ua = ip, ua

    async def export(self, after=0, size=200, city=None, parent_id=None, ceiling=None,
                     checked_through=None, segment="all"):
        if segment not in ("all", "new", "old") or (segment != "all" and checked_through is None):
            raise ServiceError("INVALID_INPUT", "Old/new export segments require a review cutoff", 422)
        if checked_through is not None and (checked_through.tzinfo is None or checked_through.utcoffset() is None):
            raise ServiceError("INVALID_INPUT", "The review cutoff must include a timezone", 422)
        if checked_through is not None:
            checked_through = checked_through.astimezone(timezone.utc)
        if parent_id is not None:
            parent = await self.db.get(Category, parent_id)
            if parent is None or parent.parent_id is not None:
                raise ServiceError("INVALID_INPUT", "Select a first-level category", 422)
        if ceiling is None:
            ceiling = await self.db.scalar(select(func.max(Service.id))) or 0
        # Slice long descriptions in SQL; don't load import_data or ORM relations.
        stmt = select(Service.id, Service.name, Service.city, Service.address,
                      Service.created_at, Service.updated_at,
                      func.substr(Service.description, 1, 120).label("description"))
        stmt = stmt.where(Service.id > after, Service.id <= ceiling)
        if checked_through is not None:
            changed_at = func.greatest(Service.created_at, Service.updated_at)
            if segment == "new":
                stmt = stmt.where(changed_at > checked_through)
            elif segment == "old":
                stmt = stmt.where(changed_at <= checked_through)
        if city:
            stmt = stmt.where(func.lower(Service.city) == city.strip().lower())
        if parent_id is not None:
            membership = select(ServiceCategory.service_id).join(Category, Category.id == ServiceCategory.category_id).where(
                ServiceCategory.service_id == Service.id,
                or_(Category.parent_id == parent_id, exists(select(CategoryParent.category_id).where(
                    CategoryParent.category_id == Category.id, CategoryParent.parent_id == parent_id))))
            stmt = stmt.where(exists(membership))
        rows = (await self.db.execute(stmt.order_by(Service.id).limit(size + 1))).mappings().all()
        page = rows[:size]
        ids = [r["id"] for r in page]
        phones = {i: [] for i in ids}
        if ids:
            for sid, value in (await self.db.execute(select(ServiceContact.service_id, ServiceContact.value).where(
                    ServiceContact.service_id.in_(ids), ServiceContact.type == "phone").order_by(ServiceContact.id))):
                phones[sid].append(value)
        records = [{"id": r["id"], "title": r["name"], "city": r["city"], "address": r["address"],
                    "description_excerpt": r["description"], "created_at": jsonable_encoder(r["created_at"]),
                    "updated_at": jsonable_encoder(r["updated_at"]),
                    "review_status": ("previously_checked" if checked_through is not None and
                        max(r["created_at"], r["updated_at"]) <= checked_through else "new"),
                    "phones": phones[r["id"]]} for r in page]
        return {"schema_version": "1.0", "records": records, "ceiling": ceiling,
                "next_after": ids[-1] if len(rows) > size else None}

    async def snapshots(self, ids, lock=False):
        stmt = select(Service).where(Service.id.in_(ids)).order_by(Service.id)
        if lock:
            stmt = stmt.with_for_update()
        services = (await self.db.scalars(stmt.execution_options(populate_existing=True))).all()
        if len(services) != len(ids):
            raise ServiceError("CONFLICT_OCCURRED", "A record is missing or was already merged; export/preview again", 409)
        records = {s.id: {"service": record_dict(s), "contacts": [], "categories": [], "bookmarks": []} for s in services}
        for model, key, order in ((ServiceContact, "contacts", ServiceContact.id),
                                  (ServiceCategory, "categories", ServiceCategory.category_id),
                                  (ServiceBookmark, "bookmarks", ServiceBookmark.bookmarker_id)):
            for row in (await self.db.scalars(select(model).where(model.service_id.in_(ids)).order_by(model.service_id, order))):
                records[row.service_id][key].append(record_dict(row))
        return list(records.values())

    async def run(self, batch):
        results = []
        for group in batch.groups:
            try:
                result = await self.group(group, batch.preview)
                if batch.preview:
                    await self.db.rollback()
                else:
                    await self.db.commit()
                results.append(result)
            except (ServiceError, SQLAlchemyError) as exc:
                await self.db.rollback()
                results.append({"keep_id": group.keep_id, "remove_ids": group.remove_ids, "action": "error",
                                "message": exc.message if isinstance(exc, ServiceError) else "Database conflict; preview again"})
        return {"schema_version": "1.0", "preview": batch.preview, "results": results}

    async def group(self, group, preview):
        # Same lock as the importer: an import cannot recreate a just-removed row
        # between archiving its identity and deleting it.
        await self.db.execute(text("SELECT pg_advisory_xact_lock(606125199)"))
        ids = sorted([group.keep_id, *group.remove_ids])
        archived = (await self.db.scalars(select(Archive).where(Archive.original_id.in_(group.remove_ids)))).all()
        if archived:
            if (len(archived) == len(group.remove_ids) and all(a.survivor_id == group.keep_id for a in archived)
                    and await self.db.get(Service, group.keep_id) is not None):
                return {"keep_id": group.keep_id, "remove_ids": group.remove_ids, "action": "already_applied"}
            raise ServiceError("CONFLICT_OCCURRED", "Group overlaps an earlier merge; preview a fresh export", 409)
        records = await self.snapshots(ids, lock=True)
        # A preview of the earlier field-combining behavior must not authorize
        # this operation: staff need to see the new keep-one/discard-other plan.
        token = fingerprint({"policy": "keep-whole-record-v1", "keep_id": group.keep_id, "records": records})
        plan = merge_plan(records, group.keep_id)
        result = {"keep_id": group.keep_id, "remove_ids": group.remove_ids, "reason": group.reason,
                  "confidence": group.confidence, "preview_token": token, "records": records, "plan": plan}
        if preview:
            return {**result, "action": "blocked" if plan["blocked"] else "preview"}
        if group.confidence != "likely":
            raise ServiceError("INVALID_INPUT", "Possible matches are review-only; confirm the group as likely and preview again", 422)
        if not group.preview_token or group.preview_token != token:
            raise ServiceError("CONFLICT_OCCURRED", "Records changed or preview is missing; preview again before applying", 409)
        if plan["blocked"]:
            raise ServiceError("CONFLICT_OCCURRED", "; ".join(plan["blocked"]), 409)
        keeper_before = next(r for r in records if r["service"]["id"] == group.keep_id)
        # Full snapshots include every service column, source text, category,
        # contact and bookmark, plus the keeper before the merge. No media is deleted.
        for record in records:
            row = record["service"]
            if row["id"] == group.keep_id:
                continue
            self.db.add(Archive(original_id=row["id"], survivor_id=group.keep_id,
                                source=row["source"], external_id=row["external_id"],
                                snapshot={"removed": record, "keeper_before": keeper_before},
                                merged_by=self.admin.username, reason=group.reason))
        await self.db.flush()
        # Repoint older archives if today's keeper was itself a previous survivor.
        await self.db.execute(update(Archive).where(Archive.survivor_id.in_(group.remove_ids)).values(survivor_id=group.keep_id))
        for record in records:
            if record["service"]["id"] == group.keep_id:
                continue
            for b in record["bookmarks"]:
                statement = insert(ServiceBookmark).values(bookmarker_id=b["bookmarker_id"],
                    service_id=group.keep_id, created_at=datetime.fromisoformat(b["created_at"]))
                await self.db.execute(statement.on_conflict_do_update(
                    index_elements=[ServiceBookmark.bookmarker_id, ServiceBookmark.service_id],
                    set_={"created_at": func.least(ServiceBookmark.created_at, statement.excluded.created_at)}))
        await self.db.flush()
        for model in (ServiceBookmark, ServiceContact, ServiceCategory):
            await self.db.execute(delete(model).where(model.service_id.in_(group.remove_ids)))
        await self.db.execute(delete(Service).where(Service.id.in_(group.remove_ids)))
        await AdminAuditRepository(self.db).record_action(admin_id=self.admin.id, admin_username=self.admin.username,
            action="service.duplicates_merge", target_type="service", target_id=group.keep_id,
            changes={"removed_ids": group.remove_ids, "reason": group.reason, "preview_token": token},
            ip_address=self.ip, user_agent=self.ua)
        return {"keep_id": group.keep_id, "remove_ids": group.remove_ids, "action": "merged"}
