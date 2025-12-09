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

class TelegramClient:
    def __init__(self):
        # We do NOT initialize the client here. 
        # We wait for the 'start' method to be called by main.py
        self.client: Optional[httpx.AsyncClient] = None
        self.token = settings.TELEGRAM_BOT_TOKEN
        self.base_url = settings.TELEGRAM_BASE_URL

    async def start(self):
        """Called by FastAPI startup event to open the connection pool."""
        logger.info("Initializing Telegram HTTP Client...")
        self.client = httpx.AsyncClient(
            base_url=f"{self.base_url}/bot{self.token}",
            timeout=10.0
        )

    async def stop(self):
        """Called by FastAPI shutdown event to close the connection pool."""
        if self.client:
            logger.info("Closing Telegram HTTP Client...")
            await self.client.aclose()
            self.client = None

    async def send_request(
        self, 
        endpoint: str, 
        payload: Dict[str, Any], 
        retry_on_429: bool = False
    ) -> TelegramResponse:
        """
        Sends a request using the persistent client if available, 
        otherwise creates a temporary one (fallback for scripts).
        """
        if self.client:
            return await self._perform_request(self.client, endpoint, payload, retry_on_429)
        else:
            # Fallback: Create a temporary client (e.g., for scripts running outside main.py)
            async with httpx.AsyncClient(base_url=f"{self.base_url}/bot{self.token}", timeout=10.0) as temp_client:
                return await self._perform_request(temp_client, endpoint, payload, retry_on_429)

    async def _perform_request(self, client: httpx.AsyncClient, endpoint: str, payload: dict, retry_on_429: bool):
        """Internal logic to handle retries and parsing."""
        try:
            # We append the endpoint to the base_url defined in the client
            url = endpoint 
            
            while True:
                response = await client.post(url, json=payload)
                
                # --- SCENARIO 1: SUCCESS (200 OK) ---
                if response.status_code == 200:
                    return TelegramResponse(success=True, status_code=200, data=response.json())
                
                # --- SCENARIO 2: RATE LIMIT (429) ---
                if response.status_code == 429:
                    data = response.json()
                    retry_after = data.get("parameters", {}).get("retry_after", 1)
                    
                    if retry_on_429:
                        logger.warning(f"Telegram 429. Sleeping {retry_after}s.")
                        await asyncio.sleep(retry_after)
                        continue
                    else:
                        return TelegramResponse(
                            success=False, status_code=429, data=data, error_message="Rate limit exceeded"
                        )

                # --- SCENARIO 3: OTHER ERRORS ---
                return TelegramResponse(
                    success=False, status_code=response.status_code, data=response.json(),
                    error_message=f"Telegram Error: {response.text}"
                )

        except httpx.RequestError as exc:
            logger.error(f"Network error requesting Telegram: {exc}")
            return TelegramResponse(success=False, status_code=0, error_message=str(exc))

    async def get_file_path(self, file_id: str) -> Optional[str]:
        payload = {"file_id": file_id}
        response = await self.send_request("getFile", payload, retry_on_429=True)
        if response.success:
            return response.data.get("result", {}).get("file_path")
        return None

    async def download_file(self, file_path: str) -> Optional[bytes]:
        """
        Downloads raw bytes. 
        Note: httpx allows absolute URLs to override the client's base_url.
        """
        file_url = f"{self.base_url}/file/bot{self.token}/{file_path}"
        
        # We define a helper to perform the get
        async def _do_download(client_instance):
            try:
                resp = await client_instance.get(file_url, timeout=30.0)
                if resp.status_code == 200:
                    return resp.content
                logger.error(f"Failed to download file: {resp.status_code}")
                return None
            except Exception as e:
                logger.error(f"Exception downloading file: {e}")
                return None

        # Use shared client if exists, else temp
        if self.client:
            return await _do_download(self.client)
        else:
            async with httpx.AsyncClient() as temp_client:
                return await _do_download(temp_client)

# --- GLOBAL INSTANCE ---
telegram_client = TelegramClient()