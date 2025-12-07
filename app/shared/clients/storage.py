import boto3
import asyncio
from botocore.exceptions import NoCredentialsError
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

class StorageClient:
    def __init__(self):
        self.s3_client = boto3.client(
            's3',
            endpoint_url=settings.R2_ENDPOINT_URL,
            aws_access_key_id=settings.R2_ACCESS_KEY_ID,
            aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY
        )
        self.bucket = settings.R2_BUCKET_NAME

    def upload_sync(self, file_bytes: bytes, destination_key: str, content_type: str = "image/jpeg"):
        """Synchronous upload function"""
        try:
            self.s3_client.put_object(
                Bucket=self.bucket,
                Key=destination_key,
                Body=file_bytes,
                ContentType=content_type
            )
            return True
        except Exception as e:
            logger.error(f"R2 Upload Failed: {e}")
            return False

    async def upload_file(self, file_bytes: bytes, file_name: str, content_type: str = "image/jpeg") -> str:
        """
        Async wrapper that offloads the blocking upload to a thread.
        Returns the Public URL (or just the key) if successful.
        """
        loop = asyncio.get_running_loop()
        
        # Run the synchronous boto3 code in a separate thread
        success = await loop.run_in_executor(
            None, 
            lambda: self.upload_sync(file_bytes, file_name, content_type)
        )

        if success:
            # Construct public URL (Assuming you have a public domain for R2)
            # If not, just return the file_name (Key)
            return f"{settings.R2_ENDPOINT_URL}/{self.bucket}/{file_name}"
        return None