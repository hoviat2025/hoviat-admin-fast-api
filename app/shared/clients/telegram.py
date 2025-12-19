import httpx
import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional
from app.core.config import settings

logger = logging.getLogger(__name__)

@dataclass
class TelegramResponse:
    success: bool
    status_code: int
    data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None

class TelegramSystem:
    """
    The Engine. 
    Manages the single HTTP connection pool to Telegram's servers.
    This is a Singleton.
    """
    def __init__(self):
        self.client: Optional[httpx.AsyncClient] = None
        self.base_url = settings.TELEGRAM_BASE_URL # e.g. https://api.telegram.org

    async def start(self):
        """Initialize the shared connection pool."""
        logger.info("Initializing Shared Telegram Connection Pool...")
        # We DO NOT put the token in the base_url anymore.
        # We just connect to the API host.
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=90,
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=100)
        )

    async def stop(self):
        """Close the pool."""
        if self.client:
            logger.info("Closing Telegram Connection Pool...")
            await self.client.aclose()
            self.client = None

    async def _raw_request(self, token: str, endpoint: str, payload: Dict, retry_on_429: bool) -> TelegramResponse:
        """
        Internal method to execute the request using the specific token.
        """
        # Construct URL dynamically based on the specific bot token
        url = f"/bot{token}/{endpoint}"
        
        # Select client (Shared or Fallback)
        if self.client:
            return await self._execute(self.client, url, payload, retry_on_429)
        else:
            # Fallback for scripts
            async with httpx.AsyncClient(base_url=self.base_url, timeout=10.0) as temp_client:
                return await self._execute(temp_client, url, payload, retry_on_429)

    async def _execute(self, client, url, payload, retry_on_429):
        try:
            while True:
                response = await client.post(url, json=payload)
                
                # Success
                if response.status_code == 200:
                    return TelegramResponse(success=True, status_code=200, data=response.json())
                
                # Rate Limit
                if response.status_code == 429:
                    data = response.json()
                    retry_after = data.get("parameters", {}).get("retry_after", 1)
                    
                    if retry_on_429:
                        logger.warning(f"Telegram Rate Limit. Sleeping {retry_after}s.")
                        await asyncio.sleep(retry_after)
                        continue
                    else:
                        return TelegramResponse(success=False, status_code=429, data=data, error_message="Rate limit exceeded")

                # Other Errors
                return TelegramResponse(
                    success=False, status_code=response.status_code, data=response.json(),
                    error_message=f"Telegram Error: {response.text}"
                )
        except httpx.RequestError as exc:
            logger.error(f"Network Error: {exc}")
            return TelegramResponse(success=False, status_code=0, error_message=str(exc))
            
    async def download_file(self, token: str, file_path: str) -> Optional[bytes]:
        url = f"/file/bot{token}/{file_path}"
        
        async def _do_get(c):
            try:
                resp = await c.get(url, timeout=90.0)
                return resp.content if resp.status_code == 200 else None
            except Exception as e:
                logger.error(f"Download error: {e}")
                return None

        if self.client:
            return await _do_get(self.client)
        else:
            async with httpx.AsyncClient(base_url=self.base_url) as temp:
                return await _do_get(temp)


# The Global Engine Instance
telegram_system = TelegramSystem()


class TelegramBot:
    """
    A specific bot instance. 
    Lightweight wrapper around the system.
    """
    def __init__(self, token: str):
        self.token = token
        # They all share the same system instance
        self.system = telegram_system

    async def send_request(self, endpoint: str, payload: Dict[str, Any], retry_on_429: bool = False) -> TelegramResponse:
        return await self.system._raw_request(self.token, endpoint, payload, retry_on_429)

    async def get_file_path(self, file_id: str) -> Optional[str]:
        resp = await self.send_request("getFile", {"file_id": file_id})
        if resp.success:
            return resp.data.get("result", {}).get("file_path")
        return None

    async def download_file(self, file_path: str) -> Optional[bytes]:
        return await self.system.download_file(self.token, file_path)