"""Cover ownership/concurrency boundaries; all database and R2 work is mocked."""

import io
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI, UploadFile
from httpx import ASGITransport, AsyncClient
from PIL import Image

from app.core.exceptions import ServiceError
from app.modules.services.services.service_media import ServiceMediaService
from app.modules.sns.dependencies import get_current_sns_user
from app.modules.sns.owned_services.router import get_owned_service_service, router
from app.modules.sns.owned_services.service import OwnedServiceService

NOW = datetime(2026, 10, 29, tzinfo=timezone.utc)
MODULE = "app.modules.services.services.service_media"


def image_file():
    data = io.BytesIO()
    Image.new("RGB", (4, 4), "blue").save(data, format="PNG")
    data.seek(0)
    return UploadFile(file=data, filename="cover.png")


class OwnerMediaTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.db = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
        self.service = ServiceMediaService(self.db)
        self.row = SimpleNamespace(owner_user_id=40, updated_at=NOW, cover_image_path=None)
        self.repo = SimpleNamespace(get_for_update=AsyncMock(return_value=self.row), update=AsyncMock())
        self.service.domain.services = self.repo
        self.service.domain.get = AsyncMock(return_value="refreshed")
        self.storage = SimpleNamespace(
            require_writes_enabled=lambda: None,
            upload_object=AsyncMock(return_value=True),
            delete_object=AsyncMock(return_value=True),
        )
        self.patch_storage = patch(f"{MODULE}.storage_client", self.storage)
        self.patch_storage.start()
        self.addCleanup(self.patch_storage.stop)

    async def test_unknown_unassigned_and_other_owner_cannot_upload_or_remove(self):
        for row in (None, SimpleNamespace(owner_user_id=None), SimpleNamespace(owner_user_id=99)):
            self.repo.get_for_update.return_value = row
            for operation in ("replace", "remove"):
                with self.subTest(row=row, operation=operation), self.assertRaises(ServiceError) as caught:
                    if operation == "replace":
                        await self.service.replace(11, image_file(), NOW, owner_user_id=40)
                    else:
                        await self.service.remove(11, NOW, owner_user_id=40)
                self.assertEqual(caught.exception.status_code, 404)
        self.storage.upload_object.assert_not_awaited()
        self.storage.delete_object.assert_not_awaited()
        self.repo.update.assert_not_awaited()
        self.db.commit.assert_not_awaited()

    async def test_stale_version_rejects_both_actions_before_storage(self):
        for operation in ("replace", "remove"):
            with self.subTest(operation=operation), self.assertRaises(ServiceError) as caught:
                if operation == "replace":
                    await self.service.replace(11, image_file(), NOW - timedelta(seconds=1), owner_user_id=40)
                else:
                    await self.service.remove(11, NOW - timedelta(seconds=1), owner_user_id=40)
            self.assertEqual(caught.exception.status_code, 409)
        self.storage.upload_object.assert_not_awaited()
        self.storage.delete_object.assert_not_awaited()
        self.repo.update.assert_not_awaited()

    async def test_owner_upload_reuses_managed_r2_key_and_normalized_jpeg(self):
        with patch(f"{MODULE}.service_media_base", return_value="https://media.example.test"):
            result = await self.service.replace(11, image_file(), NOW, owner_user_id=40)
        self.assertEqual(result, "refreshed")
        data, key, content_type, _ = self.storage.upload_object.await_args.args
        self.assertRegex(key, r"^business-covers/11/[a-f0-9]{32}\.jpg$")
        self.assertEqual(content_type, "image/jpeg")
        with Image.open(io.BytesIO(data)) as image:
            self.assertEqual(image.format, "JPEG")
        self.repo.update.assert_awaited_once_with(11, {"cover_image_path": key})
        self.db.commit.assert_awaited_once()

    async def test_owner_removal_deletes_only_after_database_commit(self):
        key = "business-covers/11/" + "a" * 32 + ".jpg"
        self.row.cover_image_path = key
        events = []
        self.db.commit.side_effect = lambda: events.append("commit")
        self.storage.delete_object.side_effect = lambda _: events.append("delete") or True
        await self.service.remove(11, NOW, owner_user_id=40)
        self.assertEqual(events, ["commit", "delete"])
        self.repo.update.assert_awaited_once_with(11, {"cover_image_path": None})
        self.storage.delete_object.assert_awaited_once_with(key)

    async def test_admin_call_without_owner_guard_remains_supported(self):
        self.row.owner_user_id = 99
        await self.service.remove(11, NOW)
        self.db.commit.assert_awaited_once()

    async def test_owner_response_is_reauthorized_after_media_commit(self):
        owner = OwnedServiceService(self.db)
        owner.get = AsyncMock(side_effect=ServiceError("SERVICE_NOT_FOUND", "Service not found", 404))
        for action in ("replace_cover_image", "remove_cover_image"):
            media = SimpleNamespace(replace=AsyncMock(), remove=AsyncMock())
            with patch("app.modules.sns.owned_services.service.ServiceMediaService", return_value=media):
                with self.subTest(action=action), self.assertRaises(ServiceError):
                    if action == "replace_cover_image":
                        file = image_file()
                        try:
                            await owner.replace_cover_image(40, 11, file, NOW)
                        finally:
                            await file.close()
                        media.replace.assert_awaited_once_with(11, file, NOW, owner_user_id=40)
                    else:
                        await owner.remove_cover_image(40, 11, NOW)
                        media.remove.assert_awaited_once_with(11, NOW, owner_user_id=40)
        self.assertEqual(owner.get.await_count, 2)


class OwnerMediaRequestTests(unittest.IsolatedAsyncioTestCase):
    async def test_cover_requests_require_a_version_and_positive_listing_id(self):
        app = FastAPI()
        app.include_router(router, prefix="/me/services")
        service = SimpleNamespace(replace_cover_image=AsyncMock(), remove_cover_image=AsyncMock())
        app.dependency_overrides[get_current_sns_user] = lambda: SimpleNamespace(user_id=40)
        app.dependency_overrides[get_owned_service_service] = lambda: service
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            upload = await client.post("/me/services/11/cover-image", files={"file": ("cover.png", b"data", "image/png")})
            removal = await client.delete("/me/services/11/cover-image")
            invalid_id = await client.delete("/me/services/0/cover-image", params={"expected_updated_at": NOW.isoformat()})
        self.assertEqual([upload.status_code, removal.status_code, invalid_id.status_code], [422, 422, 422])
        service.replace_cover_image.assert_not_awaited()
        service.remove_cover_image.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
