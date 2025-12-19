import httpx
import asyncio
import logging
from typing import Any, Dict, Optional
from dataclasses import dataclass
from app.core.config import settings

logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
BASE_URL = settings.TELEGRAM_BASE_URL
PROXY_SECRET = getattr(settings, "PROXY_SECRET", None)

# Spoof a real browser to prevent Cloudflare from "tar-pitting" (hanging) the request
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
}

if PROXY_SECRET:
    HEADERS["X-My-Proxy-Secret"] = PROXY_SECRET


@dataclass
class TelegramResponse:
    success: bool
    status_code: int
    data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None


async def _raw_http_post(url: str, payload: Dict, retry_on_429: bool = True) -> TelegramResponse:
    """
    Bare-metal HTTP POST. 
    Opens a fresh connection, sends data, closes connection. 
    Zero pooling.
    """
    transport = httpx.AsyncHTTPTransport(retries=2)  # Retry twice on connection drops

    async with httpx.AsyncClient(transport=transport, timeout=25.0, headers=HEADERS) as client:
        try:
            response = await client.post(url, json=payload)
            
            # 1. Success
            if response.status_code == 200:
                return TelegramResponse(success=True, status_code=200, data=response.json())

            # 2. Rate Limit handling
            if response.status_code == 429:
                data = response.json()
                retry_after = data.get("parameters", {}).get("retry_after", 1)
                
                if retry_on_429 and retry_after < 30: # Don't sleep if it asks for > 30s
                    logger.warning(f"Telegram 429. Sleeping {retry_after}s...")
                    await asyncio.sleep(retry_after)
                    # RECURSIVE RETRY (simple way to retry this function)
                    return await _raw_http_post(url, payload, retry_on_429=False)
                
                return TelegramResponse(success=False, status_code=429, data=data, error_message="Rate limit exceeded")

            # 3. Other Errors
            return TelegramResponse(
                success=False, 
                status_code=response.status_code, 
                error_message=f"HTTP {response.status_code}: {response.text}"
            )

        except httpx.TimeoutException:
            logger.error("Telegram Request Timed Out (25s)")
            return TelegramResponse(success=False, status_code=408, error_message="Request Timed Out")
        except Exception as e:
            logger.error(f"Telegram Connection Error: {e}")
            return TelegramResponse(success=False, status_code=0, error_message=str(e))


async def _raw_http_get_bytes(url: str) -> Optional[bytes]:
    """Bare-metal GET for files."""
    try:
        async with httpx.AsyncClient(timeout=60.0, headers=HEADERS) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                return resp.content
            return None
    except Exception as e:
        logger.error(f"File Download Error: {e}")
        return None


class TelegramBot:
    """
    Just holds the token. Logic is now in the standalone functions above.
    """
    def __init__(self, token: str):
        self.token = token

    async def send_request(self, endpoint: str, payload: Dict[str, Any], retry_on_429: bool = False) -> TelegramResponse:
        url = f"{BASE_URL}/bot{self.token}/{endpoint}"
        return await _raw_http_post(url, payload, retry_on_429)

    async def get_file_path(self, file_id: str) -> Optional[str]:
        # Simple wrapper using the same generic sender
        resp = await self.send_request("getFile", {"file_id": file_id})
        if resp.success:
            return resp.data.get("result", {}).get("file_path")
        return None

    async def download_file(self, file_path: str) -> Optional[bytes]:
        url = f"{BASE_URL}/file/bot{self.token}/{file_path}"
        return await _raw_http_get_bytes(url)

# No more 'telegram_system' instance needed.