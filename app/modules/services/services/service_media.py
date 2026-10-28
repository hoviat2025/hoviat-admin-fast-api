"""Bounded cover uploads with row locking, optimistic concurrency and cleanup."""

import asyncio
import io
import logging
from datetime import datetime
from uuid import uuid4

from fastapi import UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.exceptions import ServiceError
from app.modules.services.media_urls import is_managed_cover_key, service_media_base
from app.modules.services.services.service_service import BeforeCommit, ServiceService
from app.modules.services.validation import updated_at_conflicts
from app.shared.clients.storage import storage_client

logger = logging.getLogger(__name__)
MAX_COVER_BYTES = 5 * 1024 * 1024
MAX_COVER_DIMENSION = 10_000
MAX_COVER_PIXELS = 25_000_000
_IMAGE_WORK = asyncio.Semaphore(2)


class ServiceMediaService:
    def __init__(self, db):
        self.db = db
        self.domain = ServiceService(db)

    async def _locked_service(
        self, service_id: int, expected_updated_at: datetime,
        *, owner_user_id: int | None = None,
    ):
        service = await self.domain.services.get_for_update(service_id)
        # Check the freshly locked row, not a prior ownership lookup: an admin
        # may have reassigned the listing while the upload request was pending.
        if service is None or (owner_user_id is not None and service.owner_user_id != owner_user_id):
            raise ServiceError("SERVICE_NOT_FOUND", "Service not found", 404)
        if updated_at_conflicts(service.updated_at, expected_updated_at):
            raise ServiceError(
                "CONFLICT_OCCURRED", "This service changed; reload it before changing its cover image.", 409
            )
        return service

    async def replace(
        self, service_id: int, file: UploadFile, expected_updated_at: datetime,
        *, before_commit: BeforeCommit | None = None, owner_user_id: int | None = None,
    ):
        new_key = None
        committed = False
        try:
            storage_client.require_writes_enabled()
            service = await self._locked_service(service_id, expected_updated_at, owner_user_id=owner_user_id)
            if not service_media_base():
                raise ServiceError("SERVICE_MEDIA_NOT_CONFIGURED", "A public service media URL must be configured before uploading covers.", 503)
            raw = await self._read_bounded(file)
            try:
                async with _IMAGE_WORK:
                    normalized = await asyncio.to_thread(self._normalize, raw)
            except ServiceError:
                raise
            except (Image.DecompressionBombError, Image.DecompressionBombWarning):
                raise ServiceError("IMAGE_DIMENSIONS_EXCEEDED", "Image dimensions are too large.", 422)
            except (UnidentifiedImageError, OSError, ValueError):
                raise ServiceError("INVALID_COVER_IMAGE", "Upload a valid JPEG, PNG or WebP image.", 422)

            old_key = service.cover_image_path
            new_key = f"business-covers/{service_id}/{uuid4().hex}.jpg"
            try:
                uploaded = await storage_client.upload_object(
                    normalized, new_key, "image/jpeg", "public, max-age=31536000, immutable"
                )
            except Exception:
                logger.exception("Business cover upload failed")
                uploaded = False
            if not uploaded:
                raise ServiceError("COVER_IMAGE_UPLOAD_FAILED", "The cover image could not be uploaded. Try again.", 502)

            await self.domain.services.update(service_id, {"cover_image_path": new_key})
            if before_commit is not None:
                await before_commit(service_id)
            await self.db.commit()
            committed = True
            await self._delete_safely(old_key, service_id)
            return await self.domain.get(service_id)
        except Exception:
            if not committed:
                await self.db.rollback()
                await self._delete_safely(new_key, service_id)
            raise
        finally:
            await file.close()

    async def remove(
        self, service_id: int, expected_updated_at: datetime,
        *, before_commit: BeforeCommit | None = None, owner_user_id: int | None = None,
    ):
        try:
            storage_client.require_writes_enabled()
            service = await self._locked_service(service_id, expected_updated_at, owner_user_id=owner_user_id)
            old_key = service.cover_image_path
            if old_key is not None:
                await self.domain.services.update(service_id, {"cover_image_path": None})
                if before_commit is not None:
                    await before_commit(service_id)
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            raise
        await self._delete_safely(old_key, service_id)
        return await self.domain.get(service_id)

    @staticmethod
    async def _read_bounded(file: UploadFile) -> bytes:
        if file.size is not None and file.size > MAX_COVER_BYTES:
            raise ServiceError("IMAGE_TOO_LARGE", "The cover image must be 5 MB or smaller.", 413)
        data = bytearray()
        while chunk := await file.read(64 * 1024):
            data.extend(chunk)
            if len(data) > MAX_COVER_BYTES:
                raise ServiceError("IMAGE_TOO_LARGE", "The cover image must be 5 MB or smaller.", 413)
        if not data:
            raise ServiceError("INVALID_COVER_IMAGE", "The uploaded image is empty.", 422)
        return bytes(data)

    @staticmethod
    def _normalize(raw: bytes) -> bytes:
        with Image.open(io.BytesIO(raw)) as inspected:
            if inspected.format not in {"JPEG", "PNG", "WEBP"}:
                raise ServiceError("INVALID_IMAGE_FORMAT", "Only JPEG, PNG and WebP are supported.", 422)
            width, height = inspected.size
            if max(width, height) > MAX_COVER_DIMENSION or width * height > MAX_COVER_PIXELS:
                raise ServiceError("IMAGE_DIMENSIONS_EXCEEDED", "The cover image dimensions are too large.", 422)
            inspected.verify()
        with Image.open(io.BytesIO(raw)) as original:
            image = ImageOps.exif_transpose(original)
            image.thumbnail((1600, 1000), Image.Resampling.LANCZOS)
            # Flatten alpha on white and emit a fresh JPEG without EXIF/GPS or
            # animation metadata. Preserve aspect ratio; do not invent a crop.
            rgba = image.convert("RGBA")
            flattened = Image.new("RGB", rgba.size, "white")
            flattened.paste(rgba, mask=rgba.getchannel("A"))
            output = io.BytesIO()
            flattened.save(output, format="JPEG", quality=88, optimize=True)
            return output.getvalue()

    @staticmethod
    async def _delete_safely(key: str | None, service_id: int):
        # Only this listing's generated keys are eligible for deletion. Never
        # fetch/delete arbitrary URLs or a key supplied by a JSON client.
        if not is_managed_cover_key(key) or not key.startswith(f"business-covers/{service_id}/"):
            return
        try:
            if not await storage_client.delete_object(key):
                logger.warning("Unused business cover could not be deleted for service %s", service_id)
        except Exception:
            logger.exception("Unused business cover cleanup failed for service %s", service_id)
