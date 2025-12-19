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
    Manages HTTP requests to Telegram's servers via the proxy.
    Operates statelessly: creates a new connection for every request 
    to avoid proxy connection drops/timeouts.
    """
    def __init__(self):
        self.base_url = settings.TELEGRAM_BASE_URL 
        # Ensure you add PROXY_SECRET to your settings/env if you implement the secure worker
        self.proxy_secret = getattr(settings, "PROXY_SECRET", None)

    async def _create_client(self) -> httpx.AsyncClient:
        """
        Creates a fresh client with automatic retries for network errors.
        """
        # transport retries handles the "connection reset" or "peer closed" errors
        transport = httpx.AsyncHTTPTransport(retries=3)
        
        headers = {}
        if self.proxy_secret:
            headers["X-My-Proxy-Secret"] = self.proxy_secret

        return httpx.AsyncClient(
            base_url=self.base_url,
            timeout=90.0,
            transport=transport,
            headers=headers
        )

    async def _raw_request(self, token: str, endpoint: str, payload: Dict, retry_on_429: bool) -> TelegramResponse:
        """
        Executes the request using a fresh client instance.
        """
        url = f"/bot{token}/{endpoint}"
        
        # Create a new connection for this specific request
        async with await self._create_client() as client:
            return await self._execute(client, url, payload, retry_on_429)

    async def _execute(self, client: httpx.AsyncClient, url: str, payload: Dict, retry_on_429: bool):
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
        
        try:
            async with await self._create_client() as client:
                resp = await client.get(url)
                return resp.content if resp.status_code == 200 else None
        except Exception as e:
            logger.error(f"Download error: {e}")
            return None


# The Global Engine Instance
telegram_system = TelegramSystem()


class TelegramBot:
    """
    A specific bot instance. 
    Lightweight wrapper around the system.
    """
    def __init__(self, token: str):
        self.token = token
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