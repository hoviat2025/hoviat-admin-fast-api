import boto3
import asyncio
import logging
from typing import Optional
from botocore.exceptions import NoCredentialsError
from app.core.config import settings
from app.core.exceptions import ServiceError

logger = logging.getLogger(__name__)

class StorageClient:
    def __init__(self):
        # We delay initialization to the start() method
        self.s3_client = None
        self.bucket = settings.R2_BUCKET_NAME

    def start(self):
        """
        Initializes the Boto3 client. 
        Note: Boto3 is synchronous, but initialization is fast.
        Called by main.py lifespan.
        """
        if not settings.MEDIA_WRITES_ENABLED:
            logger.info("R2 media writes are disabled; SDK client initialization skipped.")
            return
        if self.s3_client is None:
            logger.info("Initializing R2 Storage Client...")
            self.s3_client = boto3.client(
                's3',
                endpoint_url=settings.R2_ENDPOINT_URL,
                aws_access_key_id=settings.R2_ACCESS_KEY_ID,
                aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY
            )

    def stop(self):
        """
        Boto3 doesn't strictly require closing, but this keeps the 
        interface consistent with TelegramClient.
        """
        pass 

    def get_client(self):
        """Helper to ensure client exists (lazy loading for scripts)"""
        self.require_writes_enabled()
        if self.s3_client is None:
            self.start()
        return self.s3_client

    @staticmethod
    def require_writes_enabled() -> None:
        if not settings.MEDIA_WRITES_ENABLED:
            raise ServiceError(
                "MEDIA_WRITES_DISABLED",
                "Media uploads and removals are disabled in this environment.",
                503,
            )

    def upload_sync(
        self,
        file_bytes: bytes,
        destination_key: str,
        content_type: str = "image/jpeg",
        cache_control: Optional[str] = None,
    ) -> bool:
        """
        Synchronous upload function. 
        WARNING: Do not call this directly in an async view. Use upload_file().
        """
        self.require_writes_enabled()
        client = self.get_client()
        try:
            put_args = {
                "Bucket": self.bucket,
                "Key": destination_key,
                "Body": file_bytes,
                "ContentType": content_type,
            }
            if cache_control:
                put_args["CacheControl"] = cache_control
            client.put_object(**put_args)
            return True
        except Exception as e:
            logger.error(f"R2 Upload Failed: {e}")
            return False

    async def upload_file(self, file_bytes: bytes, file_name: str, content_type: str = "image/jpeg") -> Optional[str]:
        """
        Async wrapper that offloads the blocking upload to a thread.
        Returns the Public URL if successful, else None.
        """
        self.require_writes_enabled()
        loop = asyncio.get_running_loop()
        
        # Run the synchronous boto3 code in a separate thread
        # This ensures the Main Thread (FastAPI) is never blocked by S3 uploads
        success = await loop.run_in_executor(
            None, 
            lambda: self.upload_sync(file_bytes, file_name, content_type)
        )

        if success:
            # NOTE: R2_ENDPOINT_URL is usually for API calls. PROFILE_MEDIA_URL
            # should point to the public R2/custom media domain.
            base_url = settings.PROFILE_MEDIA_URL.rstrip("/")
            return f"{base_url}/{file_name}" if base_url else file_name
        
        return None

    async def upload_object(
        self,
        file_bytes: bytes,
        destination_key: str,
        content_type: str = "image/jpeg",
        cache_control: Optional[str] = None,
    ) -> bool:
        """Upload an object while keeping public URL construction out of storage."""
        self.require_writes_enabled()
        loop = asyncio.get_running_loop()

        def upload() -> bool:
            client = self.get_client()
            try:
                put_args = {
                    "Bucket": self.bucket,
                    "Key": destination_key,
                    "Body": file_bytes,
                    "ContentType": content_type,
                }
                if cache_control:
                    put_args["CacheControl"] = cache_control
                client.put_object(**put_args)
                return True
            except Exception as e:
                logger.error(f"R2 Upload Failed: {e}")
                return False

        return await loop.run_in_executor(None, upload)

    async def delete_object(self, object_key: str) -> bool:
        """Delete an object without blocking the async event loop."""
        self.require_writes_enabled()
        loop = asyncio.get_running_loop()

        def delete() -> bool:
            client = self.get_client()
            try:
                client.delete_object(Bucket=self.bucket, Key=object_key)
                return True
            except Exception as e:
                logger.error(f"R2 Delete Failed: {e}")
                return False

        return await loop.run_in_executor(None, delete)

# --- GLOBAL INSTANCE ---
storage_client = StorageClient()
