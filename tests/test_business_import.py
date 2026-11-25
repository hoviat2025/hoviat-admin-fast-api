"""Business import contract and transaction tests; never uses production data.

Integration tests opt in with BUSINESS_IMPORT_TEST_DB_URL pointing at a local
development/test DB. Every table lives in a disposable, random schema.
"""
import copy
import ast
import os
from pathlib import Path
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from urllib.parse import urlsplit
from unittest.mock import AsyncMock, patch

from pydantic import ValidationError
from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.exceptions import ServiceError
from app.models.base import Base
from app.models.service import Service
from app.models.admin import Admin
from app.models.admin_audit_log import AdminAuditLog
from app.models.category import Category
from app.models.service_bookmark import ServiceBookmark  # register reset dependencies
from app.modules.admin.service_management.schemas.import_businesses import BusinessImportBatch, BusinessImportRow, CategoryImportBatch
from app.modules.admin.service_management.services.business_import import BusinessImporter
from app.modules.admin.service_management.services.category_import import CategoryImporter
from app.modules.services.map_links import clean_google_maps_url
from app.modules.services.public.serialization import to_public_service
from app.modules.sns.owned_services.schemas import OwnedServiceResponse


def sample():
    return {
        "service": {"name": "کسب‌وکار نمونه", "description": "خدمات نمونه", "source": "telegram",
                    "external_id": "example:42:1", "country_code": None,
                    "contacts": [{"title": "تلفن", "type": "phone", "value": "+49123456789", "is_visible": True}]},
        "description_original": "🧶 متن اولیه", "google_maps_url": "https://maps.app.goo.gl/example",
        "category_assignments": [{"category_key": "test-child", "is_primary": True}],
        "metadata": {"source_ref": "p", "source_item_index": 1, "source_subitem_index": None,
                     "batch_context": {"source_refs": ["p"]}},
        "sources": [{"source_ref": "p", "channel_username": "Example", "message_id": 42, "raw_text": "متن اصلی"}],
    }


DEFINITIONS = [
    {"key": "test-root", "name": "گروه نمونه"},
    {"key": "test-child", "name": "دسته نمونه", "primary_parent_key": "test-root", "parent_keys": ["test-root"]},
]


class ImportContractTests(unittest.TestCase):
    def test_category_hierarchy_and_duplicate_definitions(self):
        cases = [
            DEFINITIONS + [DEFINITIONS[0]],
            DEFINITIONS + [{"key": "third-level", "name": "Invalid", "primary_parent_key": "test-child", "parent_keys": ["test-child"]}],
            [{"key": "blank", "name": "  "}],
            [{"key": "bad-parent", "name": "Bad", "parent_keys": ["test-root"]}],
            [{"key": "self", "name": "Self", "parent_keys": ["self"], "primary_parent_key": "self"}],
        ]
        for definitions in cases:
            with self.subTest(definitions=definitions), self.assertRaises(ValidationError):
                CategoryImportBatch(definitions=definitions, keys=[definitions[0]["key"]])
        with self.assertRaises(ValidationError):
            CategoryImportBatch(definitions=DEFINITIONS, keys=["not-defined"])

    def test_category_keys_normalize_before_matching(self):
        payload = CategoryImportBatch(definitions=[
            {"key": "TEST_ROOT", "name": "Root"},
            {"key": "TEST_CHILD", "name": "Child", "parent_keys": ["Test Root"], "primary_parent_key": "test_root"},
        ], keys=["Test Child"])
        self.assertEqual(payload.keys, ["test-child"])
        self.assertEqual(payload.definitions[1].parent_keys, ["test-root"])
        with self.assertRaises(ValidationError):
            CategoryImportBatch(definitions=[{"key": "TEST_ROOT", "name": "Root"}, {"key": "test-root", "name": "Root"}], keys=["test-root"])

    def test_unresolved_or_mismatched_identity_is_rejected(self):
        for source, external_id in [(None, None), ("telegram", "example:43:1")]:
            row = sample()
            row["service"].update(source=source, external_id=external_id)
            with self.assertRaises(ValidationError):
                BusinessImportRow.model_validate(row)

    def test_context_source_must_travel_with_record(self):
        row = sample()
        row["metadata"]["batch_context"]["source_refs"] = ["missing"]
        with self.assertRaises(ValidationError):
            BusinessImportRow.model_validate(row)

    def test_primary_and_batch_limits(self):
        row = sample()
        row["category_assignments"][0]["is_primary"] = False
        with self.assertRaises(ValidationError):
            BusinessImportRow.model_validate(row)
        with self.assertRaises(ValidationError):
            BusinessImportBatch.model_validate({"rows": [sample()] * 11})

    def test_map_links_do_not_fetch_or_rewrite(self):
        for url in ("https://maps.app.goo.gl/a?g_st=", "https://www.google.com/maps/search/?api=1&query=Berlin",
                    "https://goo.gl/maps/example"):
            self.assertEqual(clean_google_maps_url(url), url)
        for url in ("javascript:alert(1)", "https://google.com.evil.test/maps", "https://evil.test/maps", "https://user@google.com/maps"):
            with self.assertRaises(ServiceError):
                clean_google_maps_url(url)


class ImportTransactionTests(unittest.IsolatedAsyncioTestCase):
    async def test_preview_rolls_back_and_apply_commits_per_record(self):
        for preview in (True, False):
            db = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
            importer = BusinessImporter(db, SimpleNamespace(id=1, username="test"))
            importer._row = AsyncMock(return_value={"action": "created"})
            await importer.run(BusinessImportBatch(rows=[BusinessImportRow.model_validate(sample())], preview=preview))
            self.assertEqual(db.rollback.await_count, int(preview))
            self.assertEqual(db.commit.await_count, int(not preview))

    async def test_row_error_is_reported_and_rolled_back(self):
        db = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
        importer = BusinessImporter(db, SimpleNamespace(id=1, username="test"))
        importer._row = AsyncMock(side_effect=ServiceError("INVALID_INPUT", "Unknown city", 422))
        result = await importer.run(BusinessImportBatch(rows=[BusinessImportRow.model_validate(sample())], preview=False))
        self.assertEqual(result["results"][0]["action"], "error")
        db.rollback.assert_awaited_once()
        db.commit.assert_not_awaited()


@unittest.skipUnless(os.environ.get("BUSINESS_IMPORT_TEST_DB_URL"), "Local integration database not selected")
class ImportDatabaseTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        url = os.environ["BUSINESS_IMPORT_TEST_DB_URL"]
        parts = urlsplit(url)
        if parts.hostname not in ("localhost", "127.0.0.1", "::1") or not any(s in parts.path.lower() for s in ("dev", "test")):
            raise RuntimeError("Only a local development/test database is allowed")
        self.schema = "sns_import_test_" + uuid.uuid4().hex
        self.engine = create_async_engine(url)
        async with self.engine.begin() as conn:
            await conn.execute(text(f'CREATE SCHEMA "{self.schema}"'))
            isolated = await conn.execution_options(schema_translate_map={None: self.schema})
            await isolated.run_sync(Base.metadata.create_all)
        self.bound = self.engine.execution_options(schema_translate_map={None: self.schema})
        self.db = AsyncSession(self.bound, expire_on_commit=False)
        # Audit behavior is covered by the existing audit wiring suite. Avoid
        # creating unrelated admin/user accounts even in this isolated schema.
        self.audit = patch("app.modules.admin.audit.repository.AdminAuditRepository.record_action", new_callable=AsyncMock)
        self.audit.start()
        self.importer = BusinessImporter(self.db, SimpleNamespace(id=1, username="test"))

    async def asyncTearDown(self):
        self.audit.stop()
        await self.db.close()
        async with self.engine.begin() as conn:
            await conn.execute(text(f'DROP SCHEMA "{self.schema}" CASCADE'))
        await self.engine.dispose()

    def batch(self, preview=True, mode="add", row=None):
        return BusinessImportBatch.model_validate({"rows": [row or sample()], "definitions": DEFINITIONS,
                                                   "preview": preview, "mode": mode})

    async def test_multirow_preview_and_failed_row_with_database_admin(self):
        # Production auth supplies a mapped Admin in this same session. Rollback
        # expires that object, even when expire_on_commit=False.
        self.audit.stop()
        admin = Admin(username="import-regression", password_hash="not-a-login-hash")
        self.db.add(admin)
        await self.db.commit()
        admin_id = admin.id
        rows = []
        for index in range(1, 4):
            row = sample()
            row["metadata"]["source_item_index"] = index
            row["service"]["external_id"] = f"example:42:{index}"
            rows.append(row)
        preview = BusinessImportBatch(definitions=DEFINITIONS, rows=rows)
        result = await BusinessImporter(self.db, admin).run(preview)
        self.assertEqual([r["action"] for r in result["results"]], ["created"] * 3, result)
        self.assertEqual(await self.db.scalar(select(func.count()).select_from(Service)), 0)
        self.assertEqual(await self.db.scalar(select(func.count()).select_from(AdminAuditLog)), 0)

        await self.db.refresh(admin)
        broken = copy.deepcopy(rows)
        broken[0]["google_maps_url"] = "https://invalid.example/maps"
        batch = BusinessImportBatch(definitions=DEFINITIONS, rows=broken, preview=False)
        result = await BusinessImporter(self.db, admin).run(batch)
        self.assertEqual([r["action"] for r in result["results"]], ["error", "created", "created"], result)
        logs = (await self.db.execute(select(AdminAuditLog))).scalars().all()
        self.assertTrue(logs)
        self.assertTrue(all(log.admin_id == admin_id and log.admin_username == "import-regression" for log in logs))

    async def test_category_only_preview_retry_unused_suggestions_and_conflict(self):
        importer = CategoryImporter(self.db, SimpleNamespace(id=1, username="test"))
        definitions = DEFINITIONS + [{"key": "unused", "name": "Unused category", "primary_parent_key": "test-root", "parent_keys": ["test-root"]}]
        payload = CategoryImportBatch(definitions=definitions, keys=["test-child", "unused"])
        result = await importer.run(payload)
        self.assertEqual({r["key"] for r in result["results"]}, {"test-root", "test-child", "unused"})
        self.assertEqual(await self.db.scalar(select(func.count()).select_from(Category)), 0)
        await self.db.rollback()
        result = await importer.run(payload.model_copy(update={"preview": False}))
        self.assertTrue(all(r["action"] == "created" for r in result["results"]))
        result = await importer.run(payload.model_copy(update={"preview": False}))
        self.assertTrue(all(r["action"] == "skipped" for r in result["results"]))
        self.assertEqual(await self.db.scalar(select(func.count()).select_from(Category)), 3)
        self.assertEqual(await self.db.scalar(select(func.count()).select_from(Service)), 0)
        await self.db.rollback()

        # A conflict later in this request must roll back an earlier new category.
        conflicting = copy.deepcopy(definitions)
        conflicting[1]["name"] = "Conflicting name"
        conflicting.append({"key": "must-rollback", "name": "New group"})
        with self.assertRaises(ServiceError):
            await importer.run(CategoryImportBatch(definitions=conflicting, keys=["must-rollback", "test-child"], preview=False))
        self.assertEqual(await self.db.scalar(select(func.count()).select_from(Category)), 3)
        await self.db.rollback()

        # Business imports resolve to the same IDs as a categories-only import.
        result = await self.importer.run(self.batch(preview=False))
        self.assertEqual(result["results"][0]["action"], "created")
        self.assertEqual(result["results"][0]["new_categories"], [])

    async def test_category_parent_conflict_and_unknown_parent_do_not_write(self):
        importer = CategoryImporter(self.db, SimpleNamespace(id=1, username="test"))
        await importer.run(CategoryImportBatch(definitions=DEFINITIONS, keys=["test-child"], preview=False))
        changed = copy.deepcopy(DEFINITIONS)
        changed.append({"key": "other-root", "name": "Other root"})
        changed[1].update(parent_keys=["other-root"], primary_parent_key="other-root")
        with self.assertRaises(ServiceError):
            await importer.run(CategoryImportBatch(definitions=changed, keys=["test-child"], preview=False))
        missing = [{"key": "missing-child", "name": "Missing", "parent_keys": ["unknown"], "primary_parent_key": "unknown"}]
        with self.assertRaises(ServiceError):
            await importer.run(CategoryImportBatch(definitions=missing, keys=["missing-child"], preview=False))
        self.assertEqual(await self.db.scalar(select(func.count()).select_from(Category)), 2)

    async def test_reset_sql_only_empties_directory(self):
        await self.importer.run(self.batch(preview=False))
        await self.db.execute(text(f'CREATE TABLE "{self.schema}".unrelated_probe (id integer)'))
        await self.db.execute(text(f'INSERT INTO "{self.schema}".unrelated_probe VALUES (42)'))
        await self.db.commit()
        module = ast.parse(Path("scripts/deployment/reset_directory_20261125.py").read_text(encoding="utf-8"))
        sql = next(ast.literal_eval(node.value) for node in module.body if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "RESET_SQL" for t in node.targets))
        sql = sql.replace("public.", f'"{self.schema}".')
        async with self.engine.connect() as conn:
            raw = await conn.get_raw_connection()
            await raw.driver_connection.execute(sql)
        self.assertEqual(await self.db.scalar(select(func.count()).select_from(Service)), 0)
        self.assertEqual(await self.db.scalar(select(func.count()).select_from(Category)), 0)
        self.assertEqual(await self.db.scalar(text(f'SELECT id FROM "{self.schema}".unrelated_probe')), 42)

    async def test_preview_retry_update_privacy_and_failed_row(self):
        result = await self.importer.run(self.batch())
        self.assertEqual(result["results"][0]["action"], "created", result)
        self.assertEqual(await self.db.scalar(select(func.count()).select_from(Service)), 0)
        await self.db.rollback()

        result = await self.importer.run(self.batch(preview=False))
        self.assertEqual(result["results"][0]["action"], "created", result)
        sid = result["results"][0]["service_id"]
        result = await self.importer.run(self.batch(preview=False))
        self.assertEqual(result["results"][0]["action"], "skipped", result)
        self.assertEqual(await self.db.scalar(select(func.count()).select_from(Service)), 1)
        await self.db.rollback()

        # Staff publication/media/privacy choices survive an extraction update.
        await self.db.execute(update(Service).where(Service.id == sid).values(
            status="hidden", show_owner=True, owner_show_profile=False, cover_image_path="keep.webp"))
        await self.db.commit()
        row = sample()
        row["service"]["description"] = "توضیحات جدید"
        preview = await self.importer.run(self.batch(mode="update", row=row))
        row["expected_updated_at"] = preview["results"][0]["expected_updated_at"]
        result = await self.importer.run(self.batch(False, "update", row))
        self.assertEqual(result["results"][0]["action"], "updated", result)
        saved = await self.importer.db.get(Service, sid)
        self.assertEqual(saved.description, "توضیحات جدید")
        self.assertEqual(saved.status.value, "hidden")
        self.assertTrue(saved.show_owner)
        self.assertFalse(saved.owner_show_profile)
        self.assertEqual(saved.cover_image_path, "keep.webp")
        self.assertEqual(saved.google_maps_url, sample()["google_maps_url"])
        self.assertEqual(saved.description_original, sample()["description_original"])
        self.assertEqual(saved.import_data["sources"][0]["raw_text"], "متن اصلی")
        from app.modules.services.services.service_service import ServiceService
        full = await ServiceService(self.db).get(sid)
        self.assertNotIn("import_data", OwnedServiceResponse.from_service(full).model_dump())
        public = to_public_service(await ServiceService(self.db).services.get_full(sid)).model_dump()
        self.assertEqual(public["google_maps_url"], sample()["google_maps_url"])
        self.assertNotIn("import_data", public)
        self.assertNotIn("description_original", public)
        await self.db.rollback()

        # A concurrent/manual edit after preview cannot be overwritten.
        preview = await self.importer.run(self.batch(mode="update", row=row))
        row["expected_updated_at"] = preview["results"][0]["expected_updated_at"]
        await self.db.execute(update(Service).where(Service.id == sid).values(
            description="manual edit", updated_at=datetime.now(timezone.utc) + timedelta(seconds=1)))
        await self.db.commit()
        result = await self.importer.run(self.batch(False, "update", row))
        self.assertEqual(result["results"][0]["action"], "error", result)
        self.assertEqual((await self.db.get(Service, sid)).description, "manual edit")
        await self.db.rollback()

        # Invalid map/location must not leave a partially created service.
        invalid = copy.deepcopy(sample())
        invalid["metadata"]["source_item_index"] = 2
        invalid["service"]["external_id"] = "example:42:2"
        invalid["google_maps_url"] = "https://evil.test/maps"
        result = await self.importer.run(self.batch(False, row=invalid))
        self.assertEqual(result["results"][0]["action"], "error", result)
        self.assertEqual(await self.db.scalar(select(func.count()).select_from(Service)), 1)
