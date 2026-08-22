import asyncio
import io
import logging
from uuid import uuid4

from fastapi import UploadFile
from PIL import Image, ImageOps
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ServiceError
from app.models.user import User
from app.models.user_privacy_settings import PrivacyScope, UserPrivacySettings
from app.modules.sns.account.schemas.account_responses import ProfilePictureResponse
from app.modules.sns.utils import assemble_profile_url
from app.shared.clients.storage import storage_client

logger = logging.getLogger(__name__)

MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_IMAGE_DIMENSION = 10_000
MAX_IMAGE_PIXELS = 50_000_000
NORMALIZED_SIZE = (512, 512)
ALLOWED_FORMATS = frozenset({"JPEG", "PNG", "WEBP"})
IMAGE_WORK_SEMAPHORE = asyncio.Semaphore(4)

# Pillow raises a decompression-bomb error when the decoded image exceeds this
# threshold. The explicit dimension/pixel checks below remain the main policy.
Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS


class ProfileMediaService:
    """Owns authenticated SNS profile-picture upload and removal."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def replace_avatar(
        self, user: User, file: UploadFile
    ) -> ProfilePictureResponse:
        try:
            if file.size is not None and file.size > MAX_IMAGE_BYTES:
                raise ServiceError(
                    "IMAGE_TOO_LARGE", "Profile picture must be 5 MB or smaller.", 413
                )

            raw = await self._read_bounded(file)
            key = f"avatars/{user.user_id}/{uuid4().hex}.jpg"

            try:
                async with IMAGE_WORK_SEMAPHORE:
                    uploaded = await self._normalize_and_upload(raw, key)
            except ServiceError:
                raise
            except Image.DecompressionBombError:
                raise ServiceError(
                    "IMAGE_DIMENSIONS_EXCEEDED",
                    "Profile picture dimensions are too large.",
                    422,
                )
            except Exception:
                logger.exception("Profile picture processing failed")
                raise ServiceError(
                    "INVALID_PROFILE_PICTURE",
                    "The uploaded file is not a valid supported image.",
                    422,
                )

            if not uploaded:
                raise ServiceError(
                    "PROFILE_PICTURE_UPLOAD_FAILED",
                    "Profile picture could not be uploaded.",
                    502,
                )

            old_key = user.profile_path
            try:
                user.profile_path = key
                user.profile_source = "user"
                await self.db.commit()
            except Exception:
                await self.db.rollback()
                await self._delete_object_safely(key)
                raise

            await self._delete_object_safely(old_key)
            return await self._build_response(user, key)
        finally:
            await file.close()

    async def remove_avatar(self, user: User) -> ProfilePictureResponse:
        old_key = user.profile_path

        user.profile_path = None
        # A user removal is authoritative: a later bot sync must not silently
        # restore the Telegram image they deliberately removed.
        user.profile_source = "user"
        try:
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            raise

        await self._delete_object_safely(old_key)
        return await self._build_response(user, None)

    async def _read_bounded(self, file: UploadFile) -> bytes:
        buffer = bytearray()
        size = 0

        while chunk := await file.read(64 * 1024):
            size += len(chunk)
            if size > MAX_IMAGE_BYTES:
                raise ServiceError(
                    "IMAGE_TOO_LARGE", "Profile picture must be 5 MB or smaller.", 413
                )
            buffer.extend(chunk)

        if not buffer:
            raise ServiceError(
                "INVALID_PROFILE_PICTURE", "Profile picture is empty.", 422
            )

        return bytes(buffer)

    async def _normalize_and_upload(self, raw: bytes, key: str) -> bool:
        loop = asyncio.get_running_loop()

        def work() -> bool:
            normalized = self._normalize(raw)
            return storage_client.upload_sync(
                normalized,
                key,
                "image/jpeg",
                "public, max-age=31536000, immutable",
            )

        return await loop.run_in_executor(None, work)

    @staticmethod
    def _normalize(raw: bytes) -> bytes:
        with Image.open(io.BytesIO(raw)) as inspected:
            if inspected.format not in ALLOWED_FORMATS:
                raise ServiceError(
                    "INVALID_IMAGE_FORMAT",
                    "Only JPEG, PNG, and WebP images are supported.",
                    422,
                )

            if (
                inspected.width > MAX_IMAGE_DIMENSION
                or inspected.height > MAX_IMAGE_DIMENSION
                or inspected.width * inspected.height > MAX_IMAGE_PIXELS
            ):
                raise ServiceError(
                    "IMAGE_DIMENSIONS_EXCEEDED",
                    "Profile picture dimensions are too large.",
                    422,
                )

            inspected.verify()

        with Image.open(io.BytesIO(raw)) as source:
            image = ImageOps.exif_transpose(source)
            image.load()

            if image.mode in ("RGBA", "LA") or "transparency" in image.info:
                rgba = image.convert("RGBA")
                background = Image.new("RGB", rgba.size, "white")
                background.paste(rgba, mask=rgba.getchannel("A"))
                image = background
            else:
                image = image.convert("RGB")

            image = ImageOps.fit(image, NORMALIZED_SIZE, Image.Resampling.LANCZOS)
            output = io.BytesIO()
            image.save(
                output,
                format="JPEG",
                quality=85,
                optimize=True,
                progressive=True,
            )
            return output.getvalue()

    async def _build_response(
        self, user: User, profile_path: str | None
    ) -> ProfilePictureResponse:
        privacy = await self.db.scalar(
            select(UserPrivacySettings).where(
                UserPrivacySettings.user_id == user.user_id
            )
        )
        visibility = (
            privacy.profile_picture_visibility
            if privacy
            else PrivacyScope.private
        )
        return ProfilePictureResponse(
            profile_url=assemble_profile_url(profile_path),
            profile_picture_visibility=visibility,
        )

    async def _delete_object_safely(self, object_key: str | None) -> None:
        if not object_key or object_key.startswith(("http://", "https://")):
            return
        if not await storage_client.delete_object(object_key):
            logger.warning("Could not delete old profile picture: %s", object_key)
