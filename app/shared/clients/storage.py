import boto3
import asyncio
import logging
from typing import Optional
from botocore.exceptions import NoCredentialsError
from app.core.config import settings

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
        if self.s3_client is None:
            self.start()
        return self.s3_client

    def upload_sync(self, file_bytes: bytes, destination_key: str, content_type: str = "image/jpeg") -> bool:
        """
        Synchronous upload function. 
        WARNING: Do not call this directly in an async view. Use upload_file().
        """
        client = self.get_client()
        try:
            client.put_object(
                Bucket=self.bucket,
                Key=destination_key,
                Body=file_bytes,
                ContentType=content_type
            )
            return True
        except Exception as e:
            logger.error(f"R2 Upload Failed: {e}")
            return False

    async def upload_file(self, file_bytes: bytes, file_name: str, content_type: str = "image/jpeg") -> Optional[str]:
        """
        Async wrapper that offloads the blocking upload to a thread.
        Returns the Public URL if successful, else None.
        """
        loop = asyncio.get_running_loop()
        
        # Run the synchronous boto3 code in a separate thread
        # This ensures the Main Thread (FastAPI) is never blocked by S3 uploads
        success = await loop.run_in_executor(
            None, 
            lambda: self.upload_sync(file_bytes, file_name, content_type)
        )

        if success:
            # NOTE: R2_ENDPOINT_URL is usually for API calls. 
            # If you have a Custom Domain (e.g. static.myapp.com), replace the URL base below.
            return f"https://pub-4036d35baed54ee7a9504072ea49740f.r2.dev/{file_name}"
        
        return None

# --- GLOBAL INSTANCE ---
storage_client = StorageClient()