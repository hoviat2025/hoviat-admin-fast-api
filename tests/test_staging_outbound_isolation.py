"""Outbound isolation uses mocks only: no database, storage or network calls."""

from datetime import datetime, timezone
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.config import Settings
from app.core.exceptions import ServiceError
from app.modules.services.services.service_media import ServiceMediaService
from app.modules.sns.account.services.profile_media import ProfileMediaService
from app.shared.clients import storage, telegram


class StagingOutboundIsolationTests(unittest.IsolatedAsyncioTestCase):
    def assert_disabled(self, raised, code):
        self.assertEqual(raised.exception.code, code)
        self.assertEqual(raised.exception.status_code, 503)

    def test_production_defaults_are_preserved(self):
        self.assertIs(Settings.model_fields["TELEGRAM_API_ENABLED"].default, True)
        self.assertIs(Settings.model_fields["MEDIA_WRITES_ENABLED"].default, True)

    async def test_telegram_post_disabled_before_transport_or_client_creation(self):
        with patch.object(telegram.settings, "TELEGRAM_API_ENABLED", False), \
             patch.object(telegram, "_create_telegram_transport") as transport, \
             patch.object(telegram.httpx, "AsyncClient") as client:
            with self.assertRaises(ServiceError) as raised:
                await telegram._raw_http_post("https://invalid.example/bot/test", {})
            self.assert_disabled(raised, "TELEGRAM_API_DISABLED")
            transport.assert_not_called()
            client.assert_not_called()

    async def test_telegram_download_disabled_before_transport_or_client_creation(self):
        with patch.object(telegram.settings, "TELEGRAM_API_ENABLED", False), \
             patch.object(telegram, "_create_telegram_transport") as transport, \
             patch.object(telegram.httpx, "AsyncClient") as client:
            with self.assertRaises(ServiceError) as raised:
                await telegram._raw_http_get_bytes("https://invalid.example/file/test")
            self.assert_disabled(raised, "TELEGRAM_API_DISABLED")
            transport.assert_not_called()
            client.assert_not_called()

    def test_storage_start_disabled_does_not_initialize_sdk(self):
        client = storage.StorageClient()
        with patch.object(storage.settings, "MEDIA_WRITES_ENABLED", False), \
             patch.object(storage.boto3, "client") as sdk_factory:
            client.start()
            self.assertIsNone(client.s3_client)
            sdk_factory.assert_not_called()

    async def test_storage_write_paths_disabled_even_with_preexisting_client(self):
        client = storage.StorageClient()
        sdk = MagicMock()
        client.s3_client = sdk
        with patch.object(storage.settings, "MEDIA_WRITES_ENABLED", False), \
             patch.object(storage.boto3, "client") as sdk_factory:
            with self.assertRaises(ServiceError) as raised:
                client.get_client()
            self.assert_disabled(raised, "MEDIA_WRITES_DISABLED")
            with self.assertRaises(ServiceError) as raised:
                client.upload_sync(b"image", "example.jpg")
            self.assert_disabled(raised, "MEDIA_WRITES_DISABLED")
            for operation in (
                lambda: client.upload_file(b"image", "example.jpg"),
                lambda: client.upload_object(b"image", "example.jpg"),
                lambda: client.delete_object("example.jpg"),
            ):
                with self.subTest(operation=operation), self.assertRaises(ServiceError) as raised:
                    await operation()
                self.assert_disabled(raised, "MEDIA_WRITES_DISABLED")
            self.assertEqual(sdk.mock_calls, [])
            sdk_factory.assert_not_called()

    async def test_avatar_remove_disabled_before_database_or_user_mutation(self):
        db = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock(), scalar=AsyncMock())
        user = SimpleNamespace(user_id=12, profile_path="avatars/12/original.jpg", profile_source="user")
        original = vars(user).copy()
        with patch.object(storage.settings, "MEDIA_WRITES_ENABLED", False), \
             patch.object(storage.storage_client, "delete_object", new_callable=AsyncMock) as delete:
            with self.assertRaises(ServiceError) as raised:
                await ProfileMediaService(db).remove_avatar(user)
            self.assert_disabled(raised, "MEDIA_WRITES_DISABLED")
            self.assertEqual(vars(user), original)
            db.commit.assert_not_awaited()
            db.rollback.assert_not_awaited()
            db.scalar.assert_not_awaited()
            delete.assert_not_awaited()

    async def test_avatar_upload_disabled_closes_file_without_read_or_mutation(self):
        db = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock(), scalar=AsyncMock())
        user = SimpleNamespace(user_id=12, profile_path="avatars/12/original.jpg", profile_source="user")
        original = vars(user).copy()
        file = SimpleNamespace(read=AsyncMock(), close=AsyncMock())
        with patch.object(storage.settings, "MEDIA_WRITES_ENABLED", False), \
             patch.object(storage.storage_client, "upload_sync") as upload:
            with self.assertRaises(ServiceError) as raised:
                await ProfileMediaService(db).replace_avatar(user, file)
            self.assert_disabled(raised, "MEDIA_WRITES_DISABLED")
            self.assertEqual(vars(user), original)
            file.read.assert_not_awaited()
            file.close.assert_awaited_once()
            db.commit.assert_not_awaited()
            db.scalar.assert_not_awaited()
            upload.assert_not_called()

    async def test_cover_remove_disabled_keeps_503_and_does_not_load_or_edit_listing(self):
        db = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
        service = ServiceMediaService(db)
        service._locked_service = AsyncMock()
        before_commit = AsyncMock()
        with patch.object(storage.settings, "MEDIA_WRITES_ENABLED", False), \
             patch.object(storage.storage_client, "delete_object", new_callable=AsyncMock) as delete:
            with self.assertRaises(ServiceError) as raised:
                await service.remove(12, datetime.now(timezone.utc), before_commit=before_commit)
            self.assert_disabled(raised, "MEDIA_WRITES_DISABLED")
            service._locked_service.assert_not_awaited()
            db.commit.assert_not_awaited()
            before_commit.assert_not_awaited()
            delete.assert_not_awaited()

    async def test_cover_upload_disabled_keeps_503_and_closes_file(self):
        db = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
        service = ServiceMediaService(db)
        service._locked_service = AsyncMock()
        file = SimpleNamespace(read=AsyncMock(), close=AsyncMock())
        with patch.object(storage.settings, "MEDIA_WRITES_ENABLED", False), \
             patch.object(storage.storage_client, "upload_object", new_callable=AsyncMock) as upload:
            with self.assertRaises(ServiceError) as raised:
                await service.replace(12, file, datetime.now(timezone.utc))
            self.assert_disabled(raised, "MEDIA_WRITES_DISABLED")
            service._locked_service.assert_not_awaited()
            file.read.assert_not_awaited()
            file.close.assert_awaited_once()
            db.commit.assert_not_awaited()
            upload.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
