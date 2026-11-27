"""Duplicate handling tests use a disposable schema in an explicit local test DB."""
import os
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from urllib.parse import urlsplit

from pydantic import ValidationError
from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.models.base import Base
from app.models.service import Service
from app.models.category import Category, CategoryParent
from app.models.service_contact import ServiceContact
from app.models.service_category import ServiceCategory
from app.models.service_bookmark import ServiceBookmark
from app.models.service_duplicate_archive import ServiceDuplicateArchive as Archive
from app.modules.admin.service_management.schemas.duplicates import DuplicateBatch
from app.modules.admin.service_management.services.duplicates import DuplicateHandler, merge_plan
from app.modules.admin.service_management.schemas.import_businesses import BusinessImportBatch
from app.modules.admin.service_management.services.business_import import BusinessImporter


def group(keep=1, remove=None, **kw):
    return {"keep_id": keep, "remove_ids": remove or [2], "reason": "Matching distinctive name and contacts", "confidence": "likely", **kw}


class ContractTests(unittest.TestCase):
    def test_overlapping_groups_and_bad_ids_rejected(self):
        for groups in ([group(remove=[1])], [group(), group(keep=3)], [group(remove=[-1])],
                       [group(confidence="certain")], [group(reason="")]):
            with self.subTest(groups=groups), self.assertRaises(ValidationError):
                DuplicateBatch(groups=groups)

    def test_plan_keeps_privacy_and_nonempty_fields(self):
        def record(id, **values):
            return {"service": {"id": id, "owner_user_id": None, "show_owner": True,
                "owner_show_profile": True, "description": "keeper" if id == 1 else "other", **values},
                "contacts": [], "categories": [], "bookmarks": []}
        plan = merge_plan([record(1), record(2, show_owner=False)], 1)
        self.assertTrue(plan["blocked"])
        self.assertEqual(plan["operation"], "keep_unchanged_archive_others")
        self.assertEqual(plan["archive_ids"], [2])
        self.assertNotIn("fill_empty_fields", plan)
        self.assertNotIn("add_contacts", plan)
        self.assertNotIn("add_category_ids", plan)


@unittest.skipUnless(os.environ.get("BUSINESS_IMPORT_TEST_DB_URL"), "Local integration DB not selected")
class DatabaseTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        url = os.environ["BUSINESS_IMPORT_TEST_DB_URL"]
        parsed = urlsplit(url)
        if parsed.hostname not in ("localhost", "127.0.0.1", "::1") or not any(x in parsed.path for x in ("dev", "test")):
            raise RuntimeError("Only a local development/test database is permitted")
        self.schema = "sns_duplicate_test_" + uuid.uuid4().hex
        self.engine = create_async_engine(url)
        async with self.engine.begin() as conn:
            await conn.execute(text(f'CREATE SCHEMA "{self.schema}"'))
            isolated = await conn.execution_options(schema_translate_map={None: self.schema})
            await isolated.run_sync(Base.metadata.create_all)
        self.db = AsyncSession(self.engine.execution_options(schema_translate_map={None: self.schema}), expire_on_commit=False)
        self.audit = patch("app.modules.admin.audit.repository.AdminAuditRepository.record_action", new_callable=AsyncMock)
        self.audit_mock = self.audit.start()
        self.handler = DuplicateHandler(self.db, SimpleNamespace(id=1, username="test"))
        self.db.add_all([Service(id=i, name="DATO", description="original " * i,
            city="Berlin", address="Rhinstraße 72", country_code="DE", show_owner=True, owner_show_profile=True,
            source="telegram", external_id=f"test:1:{i}", status="published") for i in (1, 2, 3)])
        self.db.add_all([Category(id=100, name="Root", slug="root"), Category(id=200, name="Other", slug="other")])
        await self.db.flush()
        self.db.add_all([Category(id=101, name="Travel", slug="travel", parent_id=100),
                         Category(id=102, name="Secondary", slug="secondary", parent_id=200)])
        await self.db.flush()
        self.db.add_all([CategoryParent(category_id=101, parent_id=200),
                         ServiceCategory(service_id=1, category_id=101, is_primary=True),
                         ServiceCategory(service_id=2, category_id=102, is_primary=True),
                         ServiceContact(service_id=1, title="Phone", type="phone", value="+4912345", is_visible=True),
                         ServiceContact(service_id=2, title="Phone", type="phone", value="+4967890", is_visible=True)])
        await self.db.commit()

    async def asyncTearDown(self):
        self.audit.stop()
        await self.db.close()
        async with self.engine.begin() as conn:
            await conn.execute(text(f'DROP SCHEMA "{self.schema}" CASCADE'))
        await self.engine.dispose()

    async def run_group(self, preview=True, payload=None):
        return (await self.handler.run(DuplicateBatch(preview=preview, groups=[payload or group()])))["results"][0]

    async def previewed(self):
        preview = await self.run_group()
        self.assertEqual(preview["action"], "preview", preview)
        return group(preview_token=preview["preview_token"])

    async def test_preview_is_read_only_then_merge_archives_and_retry_is_safe(self):
        keeper_before = (await self.handler.snapshots([1]))[0]
        payload = await self.previewed()
        self.assertEqual(await self.db.scalar(select(func.count()).select_from(Service)), 3)
        self.assertEqual(await self.db.scalar(select(func.count()).select_from(Archive)), 0)
        result = await self.run_group(False, payload)
        self.assertEqual(result["action"], "merged", result)
        self.assertEqual(await self.db.scalar(select(func.count()).select_from(Service)), 2)
        archive = await self.db.get(Archive, 2)
        self.assertEqual(archive.snapshot["removed"]["service"]["description"], "original " * 2)
        self.assertEqual(archive.snapshot["keeper_before"]["service"]["id"], 1)
        keeper_after = (await self.handler.snapshots([1]))[0]
        self.assertEqual(keeper_before, keeper_after)
        self.assertEqual(await self.db.scalar(select(func.count()).select_from(ServiceContact).where(ServiceContact.service_id == 1)), 1)
        self.assertEqual(await self.db.scalar(select(func.count()).select_from(ServiceCategory).where(ServiceCategory.service_id == 1)), 1)
        self.assertEqual((await self.run_group(False, payload))["action"], "already_applied")
        self.assertEqual(self.audit_mock.await_count, 1)

    async def test_missing_keeper_fields_stay_empty_and_other_values_are_archived(self):
        await self.db.execute(update(Service).where(Service.id == 1).values(description=None, cover_image_path=None))
        await self.db.execute(update(Service).where(Service.id == 2).values(cover_image_path="business-covers/2/example.jpg"))
        # Equivalent Instagram URLs must not produce a second contact on the keeper.
        self.db.add_all([
            ServiceContact(service_id=1, title="Instagram", type="url", value="https://www.instagram.com/example", platform="instagram", is_visible=True),
            ServiceContact(service_id=2, title="Instagram", type="url", value="https://instagram.com/example", platform="instagram", is_visible=True),
        ])
        await self.db.commit()
        before = (await self.handler.snapshots([1]))[0]
        self.assertEqual((await self.run_group(False, await self.previewed()))["action"], "merged")
        self.assertEqual((await self.handler.snapshots([1]))[0], before)
        archive = await self.db.get(Archive, 2)
        self.assertEqual(archive.snapshot["removed"]["service"]["cover_image_path"], "business-covers/2/example.jpg")
        self.assertEqual(len(archive.snapshot["removed"]["contacts"]), 2)

    async def test_old_field_combining_preview_is_rejected(self):
        from app.modules.admin.service_management.services.duplicates import fingerprint
        records = await self.handler.snapshots([1, 2])
        old_token = fingerprint({"keep_id": 1, "records": records})
        result = await self.run_group(False, group(preview_token=old_token))
        self.assertEqual(result["action"], "error")
        self.assertEqual(await self.db.scalar(select(func.count()).select_from(Archive)), 0)

    async def test_changed_contact_after_preview_blocks_entire_group(self):
        payload = await self.previewed()
        await self.db.execute(update(ServiceContact).where(ServiceContact.service_id == 2).values(value="changed"))
        await self.db.commit()
        result = await self.run_group(False, payload)
        self.assertEqual(result["action"], "error")
        self.assertEqual(await self.db.scalar(select(func.count()).select_from(Archive)), 0)
        self.assertIsNotNone(await self.db.get(Service, 2))

    async def test_possible_and_privacy_conflicts_never_apply(self):
        payload = await self.previewed()
        payload["confidence"] = "possible"
        self.assertEqual((await self.run_group(False, payload))["action"], "error")
        await self.db.execute(update(Service).where(Service.id == 2).values(owner_show_profile=False))
        await self.db.commit()
        self.assertEqual((await self.run_group())["action"], "blocked")

    async def test_archive_aliases_follow_survivor_and_prevent_reimport(self):
        self.assertEqual((await self.run_group(False, await self.previewed()))["action"], "merged")
        preview = await self.run_group(payload=group(keep=3, remove=[1]))
        result = await self.run_group(False, group(keep=3, remove=[1], preview_token=preview["preview_token"]))
        self.assertEqual(result["action"], "merged", result)
        self.assertEqual((await self.db.get(Archive, 2)).survivor_id, 3)
        from test_business_import import sample
        row = sample()
        row["sources"][0]["channel_username"] = "test"
        row["sources"][0]["message_id"] = 1
        row["metadata"]["source_item_index"] = 2
        row["service"]["external_id"] = "test:1:2"
        for mode in ("add", "update"):
            result = await BusinessImporter(self.db, SimpleNamespace(id=1, username="test")).run(
                BusinessImportBatch(rows=[row], mode=mode, preview=False))
            self.assertEqual(result["results"][0]["action"], "skipped", result)
            self.assertEqual(result["results"][0]["service_id"], 3)

    async def test_export_pages_filters_secondary_parent_and_excludes_archives(self):
        await self.db.execute(update(Service).where(Service.id == 1).values(description="x" * 1000))
        await self.db.commit()
        first = await self.handler.export(size=1, city="berlin")
        self.assertEqual(first["next_after"], 1)
        self.assertEqual(len(first["records"][0]["description_excerpt"]), 120)
        self.assertEqual(first["records"][0]["phones"], ["+4912345"])
        self.assertEqual(set(first["records"][0]), {"id", "title", "city", "address", "phones", "description_excerpt", "created_at", "updated_at", "review_status"})
        second = await self.handler.export(after=first["next_after"], ceiling=first["ceiling"])
        self.assertEqual([r["id"] for r in second["records"]], [2, 3])
        filtered = await self.handler.export(parent_id=200)
        self.assertEqual([r["id"] for r in filtered["records"]], [1, 2])
        self.assertEqual((await self.handler.export(city="Paris"))["records"], [])
        await self.run_group(False, await self.previewed())
        self.assertEqual([r["id"] for r in (await self.handler.export())["records"]], [1, 3])

    async def test_incremental_cutoff_includes_edits_and_exact_boundary_is_old(self):
        cutoff = datetime(2026, 1, 1, tzinfo=timezone.utc)
        for sid, created, updated_at in ((1, cutoff - timedelta(days=1), cutoff),
                                         (2, cutoff - timedelta(days=1), cutoff + timedelta(seconds=1)),
                                         (3, cutoff + timedelta(seconds=1), cutoff + timedelta(seconds=1))):
            await self.db.execute(update(Service).where(Service.id == sid).values(created_at=created, updated_at=updated_at))
        await self.db.commit()
        page = await self.handler.export(checked_through=cutoff)
        self.assertEqual([(r["id"], r["review_status"]) for r in page["records"]],
                         [(1, "previously_checked"), (2, "new"), (3, "new")])
        fresh = await self.handler.export(checked_through=cutoff, segment="new", size=1)
        self.assertEqual([r["id"] for r in fresh["records"]], [2])
        next_page = await self.handler.export(after=fresh["next_after"], checked_through=cutoff,
                                              segment="new", ceiling=fresh["ceiling"])
        self.assertEqual([r["id"] for r in next_page["records"]], [3])
        old = await self.handler.export(checked_through=cutoff, segment="old", parent_id=200, city="Berlin")
        self.assertEqual([r["id"] for r in old["records"]], [1])
        self.assertTrue(all(r["review_status"] == "new" for r in (await self.handler.export())["records"]))

    async def test_incremental_parameters_are_validated_without_writes(self):
        from app.core.exceptions import ServiceError
        for arguments in ({"segment": "old"}, {"segment": "invalid"}, {"checked_through": datetime(2026, 1, 1)}):
            with self.subTest(arguments=arguments), self.assertRaises(ServiceError):
                await self.handler.export(**arguments)
        self.assertEqual(await self.db.scalar(select(func.count()).select_from(Archive)), 0)

    async def test_audit_failure_rolls_back_archive_and_deletions(self):
        payload = await self.previewed()
        from sqlalchemy.exc import SQLAlchemyError
        self.audit_mock.side_effect = SQLAlchemyError("simulated transaction failure")
        self.assertEqual((await self.run_group(False, payload))["action"], "error")
        self.assertEqual(await self.db.scalar(select(func.count()).select_from(Archive)), 0)
        self.assertEqual(await self.db.scalar(select(func.count()).select_from(Service)), 3)

    async def test_bookmarks_preserve_earliest_date(self):
        # Temporarily drop only the user FK in this disposable schema; no users
        # need to be created to exercise directory bookmark migration.
        async with self.engine.begin() as conn:
            constraints = (await conn.execute(text("SELECT conname FROM pg_constraint WHERE conrelid=to_regclass(:table) AND contype='f' AND confrelid=to_regclass(:users)"),
                {"table": f"{self.schema}.service_bookmarks", "users": f"{self.schema}.users_eurobot"})).scalars().all()
            for name in constraints:
                await conn.execute(text(f'ALTER TABLE "{self.schema}".service_bookmarks DROP CONSTRAINT "{name}"'))
        older = datetime.now(timezone.utc) - timedelta(days=1)
        self.db.add_all([ServiceBookmark(bookmarker_id=10, service_id=1),
                         ServiceBookmark(bookmarker_id=10, service_id=2, created_at=older),
                         ServiceBookmark(bookmarker_id=20, service_id=2, created_at=older)])
        await self.db.commit()
        result = await self.run_group(False, await self.previewed())
        self.assertEqual(result["action"], "merged", result)
        rows = (await self.db.scalars(select(ServiceBookmark).where(ServiceBookmark.service_id == 1).order_by(ServiceBookmark.bookmarker_id))).all()
        self.assertEqual([b.bookmarker_id for b in rows], [10, 20])
        self.assertEqual(rows[0].created_at, older)
        self.assertEqual(rows[1].created_at, older)

    async def test_migration_is_repeatable_and_directory_only(self):
        async with self.engine.begin() as conn:
            isolated = await conn.execution_options(schema_translate_map={None: self.schema})
            await isolated.run_sync(Archive.__table__.drop)
        from pathlib import Path
        migration = Path("scripts/database/20261127_25_business_duplicates.sql").read_text(encoding="utf-8")
        async with self.engine.connect() as conn:
            raw = await conn.get_raw_connection()
            await raw.driver_connection.execute(f'SET search_path TO "{self.schema}"')
            await raw.driver_connection.execute(migration)
            await raw.driver_connection.execute(migration)
        self.assertEqual(await self.db.scalar(select(func.count()).select_from(Archive)), 0)
        self.assertEqual(await self.db.scalar(select(func.count()).select_from(Service)), 3)
