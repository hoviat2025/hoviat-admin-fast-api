import httpx
import asyncio
import logging
from typing import Any, Dict, Optional
from dataclasses import dataclass
from app.core.config import settings

logger = logging.getLogger(__name__)

# --- API Configuration ---
BASE_URL = settings.TELEGRAM_BASE_URL
PROXY_SECRET = getattr(settings, "PROXY_SECRET", None)

# Request headers configured to mimic standard browser signatures.
# This reduces the likelihood of requests being intercepted or throttled by 
# intermediate security layers (e.g., Cloudflare).
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
}

if PROXY_SECRET:
    HEADERS["X-My-Proxy-Secret"] = PROXY_SECRET


@dataclass
class TelegramResponse:
    """
    Data Transfer Object (DTO) for standardized Telegram API responses.
    """
    success: bool
    status_code: int
    data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None


async def _raw_http_post(url: str, payload: Dict, retry_on_429: bool = True) -> TelegramResponse:
    """
    Executes an atomic HTTP POST request. 
    
    This helper uses a short-lived client instance for each call. While less 
    performant than connection pooling, it ensures maximum isolation and 
    prevents stale connection issues in long-running tasks.
    """
    # Configure transport with basic retry logic for network-level failures
    transport = httpx.AsyncHTTPTransport(retries=2)

    async with httpx.AsyncClient(transport=transport, timeout=25.0, headers=HEADERS) as client:
        try:
            response = await client.post(url, json=payload)
            
            # Successful request handling
            if response.status_code == 200:
                return TelegramResponse(success=True, status_code=200, data=response.json())

            # Rate limit handling (HTTP 429)
            if response.status_code == 429:
                data = response.json()
                retry_after = data.get("parameters", {}).get("retry_after", 1)
                
                # Only attempt a recursive retry if the wait time is below a 30s threshold
                if retry_on_429 and retry_after < 30:
                    logger.warning(f"Rate limited by Telegram. Retrying after {retry_after}s...")
                    await asyncio.sleep(retry_after)
                    
                    # Execute a single recursive retry attempt
                    return await _raw_http_post(url, payload, retry_on_429=False)
                
                return TelegramResponse(
                    success=False, 
                    status_code=429, 
                    data=data, 
                    error_message="Rate limit exceeded"
                )

            # Handle non-200/429 status codes
            return TelegramResponse(
                success=False, 
                status_code=response.status_code, 
                error_message=f"HTTP {response.status_code}: {response.text}"
            )

        except httpx.TimeoutException:
            logger.error("Request to Telegram timed out after 25 seconds.")
            return TelegramResponse(success=False, status_code=408, error_message="Request Timed Out")
        except Exception as e:
            logger.error(f"Unexpected connection error during Telegram communication: {e}")
            return TelegramResponse(success=False, status_code=0, error_message=str(e))


async def _raw_http_get_bytes(url: str) -> Optional[bytes]:
    """
    Internal helper for binary data retrieval (e.g., downloading media).
    """
    try:
        async with httpx.AsyncClient(timeout=60.0, headers=HEADERS) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                return resp.content
            return None
    except Exception as e:
        logger.error(f"Failed to download file from Telegram: {e}")
        return None


class TelegramBot:
    """
    Client interface for interacting with the Telegram Bot API.
    """
    def __init__(self, token: str):
        self.token = token

    async def send_request(self, endpoint: str, payload: Dict[str, Any], retry_on_429: bool = False) -> TelegramResponse:
        """
        Routes a POST request to a specific Telegram Bot API method.
        """
        url = f"{BASE_URL}/bot{self.token}/{endpoint}"
        return await _raw_http_post(url, payload, retry_on_429)

    async def get_file_path(self, file_id: str) -> Optional[str]:
        """
        Retrieves the relative file path for a Telegram file object.
        """
        resp = await self.send_request("getFile", {"file_id": file_id})
        if resp.success:
            return resp.data.get("result", {}).get("file_path")
        return None

    async def download_file(self, file_path: str) -> Optional[bytes]:
        """
        Downloads binary content for a given Telegram file path.
        """
        url = f"{BASE_URL}/file/bot{self.token}/{file_path}"
        return await _raw_http_get_bytes(url)