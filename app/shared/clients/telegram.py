import httpx
import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional
from app.core.config import settings

logger = logging.getLogger(__name__)

# 1. Define a standardized response object
@dataclass
class TelegramResponse:
    success: bool
    status_code: int
    data: Optional[Dict[str, Any]] = None  # The JSON from Telegram
    error_message: Optional[str] = None

class TelegramClient:
    def __init__(self, token: str = settings.TELEGRAM_BOT_TOKEN, base_url: str = settings.TELEGRAM_BASE_URL):
        self.token = token
        self.base_url = base_url

    async def send_request(
        self, 
        endpoint: str, 
        payload: Dict[str, Any], 
        retry_on_429: bool = False
    ) -> TelegramResponse:
        
        url = f"{self.base_url}/bot{self.token}/{endpoint}"
        
        async with httpx.AsyncClient() as client:
            try:
                while True:
                    response = await client.post(url, json=payload, timeout=10.0)
                    
                    # --- SCENARIO 1: SUCCESS (200 OK) ---
                    if response.status_code == 200:
                        return TelegramResponse(
                            success=True,
                            status_code=200,
                            data=response.json()
                        )
                    
                    # --- SCENARIO 2: RATE LIMIT (429) ---
                    if response.status_code == 429:
                        response_json = response.json()
                        retry_after = response_json.get("parameters", {}).get("retry_after", 1)
                        
                        if retry_on_429:
                            logger.warning(f"Telegram 429. Sleeping {retry_after}s.")
                            await asyncio.sleep(retry_after)
                            continue  # Loop back and try again
                        else:
                            # Return failure if we aren't allowed to retry
                            return TelegramResponse(
                                success=False,
                                status_code=429,
                                data=response_json,
                                error_message="Rate limit exceeded"
                            )

                    # --- SCENARIO 3: OTHER ERRORS (400, 401, 500, etc) ---
                    # We do NOT raise_for_status. We return the failure.
                    return TelegramResponse(
                        success=False,
                        status_code=response.status_code,
                        data=response.json(), # Telegram usually sends a description in JSON even on error
                        error_message=f"Telegram Error: {response.text}"
                    )

            except httpx.RequestError as exc:
                # This handles network failures (DNS, No Internet, etc)
                logger.error(f"Network error requesting Telegram: {exc}")
                return TelegramResponse(
                    success=False,
                    status_code=0,
                    error_message=str(exc)
                )
    
    # ... existing init and send_request ...

    async def get_file_path(self, file_id: str) -> Optional[str]:
        """
        Exchanges a file_id for a remote file_path using the getFile endpoint.
        """
        payload = {"file_id": file_id}
        # Reuse your existing robust logic!
        response = await self.send_request("getFile", payload, retry_on_429=True)
        
        if response.success:
            return response.data.get("result", {}).get("file_path")
        return None

    async def download_file(self, file_path: str) -> Optional[bytes]:
        """
        Downloads the raw binary content of a file from Telegram.
        URL Format: https://api.telegram.org/file/bot<token>/<file_path>
        """
        # Note the extra '/file/' in the URL
        # If your base_url is "https://api.telegram.org", we strip it to rebuild properly
        # or just construct it manually:
        base = self.base_url.replace("/bot", "") # quick cleanup if needed, but standard is:
        file_url = f"https://api.telegram.org/file/bot{self.token}/{file_path}"

        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(file_url, timeout=30.0)
                if resp.status_code == 200:
                    return resp.content # Returns raw bytes
                else:
                    logger.error(f"Failed to download file: {resp.status_code}")
                    return None
            except Exception as e:
                logger.error(f"Exception downloading file: {e}")
                return None