"""Saved business authorization, visibility and PostgreSQL query contracts."""

import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import httpx
from fastapi import FastAPI
from sqlalchemy.dialects import postgresql

from app.core.exceptions import ServiceError, register_exception_handlers
from app.models.service import ServiceStatus
from app.models.service_contact import ServiceContactType
from app.modules.sns.dependencies import get_current_sns_user
from app.modules.sns.service_bookmarks.dependencies import get_service_bookmark_service
from app.modules.sns.service_bookmarks.repository import ServiceBookmarkRepository
from app.modules.sns.service_bookmarks.router import router
from app.modules.sns.service_bookmarks.service import ServiceBookmarkService


def business():
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=7, name="Bakery", description="Business bio", persian_owned=True,
        persian_provider=None, persian_language=True, persian_service=False,
        address=None, postal_code=None, city="Berlin", state="Berlin",
        country_code="DE", latitude=None, longitude=None, created_at=now,
        updated_at=now, owner_user_id=999, source="private-import",
        external_id="private-id", status=ServiceStatus.published,
        contacts=[SimpleNamespace(
            title="Private telephone", type=ServiceContactType.phone,
            value="private-number", platform=None, display_order=0, is_visible=False,
        )], category_links=[],
    )


def sql(statement):
    return str(statement.compile(
        dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True},
    ))


class ServiceBookmarkRepositoryTests(unittest.IsolatedAsyncioTestCase):
    async def test_only_published_target_can_be_saved_and_duplicate_is_noop(self):
        db = SimpleNamespace(scalar=AsyncMock(return_value=7), execute=AsyncMock())
        repository = ServiceBookmarkRepository(db)
        self.assertTrue(await repository.add_published(42, 7))
        target_query = sql(db.scalar.call_args.args[0])
        self.assertIn("services.id = 7", target_query)
        self.assertIn("services.status = 'published'", target_query)
        self.assertIn("FOR SHARE", target_query)
        insertion = sql(db.execute.call_args.args[0])
        self.assertIn("(bookmarker_id, service_id) VALUES (42, 7)", insertion)
        self.assertIn("ON CONFLICT (bookmarker_id, service_id) DO NOTHING", insertion)
        db.scalar.return_value = None
        db.execute.reset_mock()
        self.assertFalse(await repository.add_published(42, 7))
        db.execute.assert_not_awaited()

    async def test_list_is_scoped_to_current_user_and_published_rows(self):
        db = SimpleNamespace(scalars=AsyncMock(return_value=Mock(all=lambda: [])))
        self.assertEqual(await ServiceBookmarkRepository(db).list_published(42), [])
        query = sql(db.scalars.call_args.args[0])
        self.assertIn("service_bookmarks.bookmarker_id = 42", query)
        self.assertIn("services.status = 'published'", query)
        self.assertIn("JOIN service_bookmarks ON service_bookmarks.service_id = services.id", query)
        self.assertIn("service_bookmarks.created_at DESC", query)

    async def test_removal_cannot_delete_another_users_bookmark(self):
        db = SimpleNamespace(execute=AsyncMock())
        await ServiceBookmarkRepository(db).remove(42, 7)
        query = sql(db.execute.call_args.args[0])
        self.assertIn("service_bookmarks.bookmarker_id = 42", query)
        self.assertIn("service_bookmarks.service_id = 7", query)


class ServiceBookmarkServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.db = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
        self.service = ServiceBookmarkService(self.db)
        self.service.repository = SimpleNamespace(
            add_published=AsyncMock(return_value=True), remove=AsyncMock(),
            list_published=AsyncMock(return_value=[business()]),
        )

    async def test_hidden_or_missing_target_is_404_without_commit(self):
        self.service.repository.add_published.return_value = False
        with self.assertRaises(ServiceError) as raised:
            await self.service.save(42, 7)
        self.assertEqual(raised.exception.code, "SERVICE_NOT_FOUND")
        self.assertEqual(raised.exception.status_code, 404)
        self.db.commit.assert_not_awaited()
        self.db.rollback.assert_awaited_once()

    async def test_duplicate_save_and_missing_remove_are_idempotent(self):
        for _ in range(2):
            await self.service.save(42, 7)
            await self.service.remove(42, 7)
        self.assertEqual(self.db.commit.await_count, 4)
        self.db.rollback.assert_not_awaited()

    async def test_list_reuses_public_privacy_projection(self):
        items, total = await self.service.list(42)
        payload = items[0].model_dump()
        self.assertEqual(total, 1)
        self.assertEqual(payload["description"], "Business bio")
        self.assertEqual(payload["contacts"], [])
        for key in ("owner_user_id", "source", "external_id", "status"):
            self.assertNotIn(key, payload)

    async def test_database_failure_rolls_back(self):
        self.db.commit.side_effect = RuntimeError("database failed")
        with self.assertRaises(RuntimeError):
            await self.service.save(42, 7)
        self.db.rollback.assert_awaited_once()


class ServiceBookmarkRouteTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.app = FastAPI()
        register_exception_handlers(self.app)
        self.app.include_router(router, prefix="/api/sns/me/service-bookmarks")
        self.service = SimpleNamespace(
            list=AsyncMock(return_value=([], 0)), save=AsyncMock(), remove=AsyncMock(),
        )
        self.app.dependency_overrides[get_service_bookmark_service] = lambda: self.service
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.app), base_url="http://test",
        )

    async def asyncTearDown(self):
        await self.client.aclose()

    async def test_anonymous_cannot_read_or_mutate(self):
        for method, suffix in (("get", ""), ("post", "/7"), ("delete", "/7")):
            response = await getattr(self.client, method)("/api/sns/me/service-bookmarks" + suffix)
            self.assertIn(response.status_code, (401, 403))
        self.service.list.assert_not_awaited()
        self.service.save.assert_not_awaited()
        self.service.remove.assert_not_awaited()

    async def test_identity_always_comes_from_authenticated_account(self):
        self.app.dependency_overrides[get_current_sns_user] = lambda: SimpleNamespace(user_id=42)
        root = "/api/sns/me/service-bookmarks"
        response = await self.client.get(root + "?bookmarker_id=999")
        self.assertEqual(response.status_code, 200)
        self.service.list.assert_awaited_once_with(42)
        for method, bookmarked in (("post", True), ("delete", False)):
            response = await getattr(self.client, method)(root + "/7?bookmarker_id=999")
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["data"], {"service_id": 7, "bookmarked": bookmarked})
        self.service.save.assert_awaited_once_with(42, 7)
        self.service.remove.assert_awaited_once_with(42, 7)

    async def test_unpublished_save_returns_generic_404(self):
        self.app.dependency_overrides[get_current_sns_user] = lambda: SimpleNamespace(user_id=42)
        self.service.save.side_effect = ServiceError("SERVICE_NOT_FOUND", "Service not found", 404)
        response = await self.client.post("/api/sns/me/service-bookmarks/7")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "SERVICE_NOT_FOUND")


if __name__ == "__main__":
    unittest.main()
