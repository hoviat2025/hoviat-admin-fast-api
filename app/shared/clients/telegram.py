import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

BASE_URL = settings.TELEGRAM_BASE_URL
PROXY_SECRET = getattr(settings, "PROXY_SECRET", None)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

if PROXY_SECRET:
    HEADERS["X-My-Proxy-Secret"] = PROXY_SECRET


def _create_telegram_transport() -> httpx.AsyncHTTPTransport:
    """
    Create a transport that uses IPv4 for Telegram.

    The VPS can reach Telegram reliably over IPv4, while its Telegram IPv6
    route stalls during connection establishment.
    """
    return httpx.AsyncHTTPTransport(
        retries=2,
        local_address="0.0.0.0",
    )


@dataclass
class TelegramResponse:
    """Standardized result returned by Telegram API requests."""

    success: bool
    status_code: int
    data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None


async def _raw_http_post(
    url: str,
    payload: Dict[str, Any],
    retry_on_429: bool = True,
) -> TelegramResponse:
    """Execute one Telegram HTTP POST request."""
    async with httpx.AsyncClient(
        transport=_create_telegram_transport(),
        timeout=25.0,
        headers=HEADERS,
        trust_env=False,
    ) as client:
        try:
            response = await client.post(url, json=payload)

            if response.status_code == 200:
                return TelegramResponse(
                    success=True,
                    status_code=200,
                    data=response.json(),
                )

            if response.status_code == 429:
                data = response.json()
                retry_after = data.get("parameters", {}).get("retry_after", 1)

                if retry_on_429 and retry_after < 30:
                    logger.warning(
                        "Rate limited by Telegram; retrying after %ss.",
                        retry_after,
                    )
                    await asyncio.sleep(retry_after)
                    return await _raw_http_post(
                        url,
                        payload,
                        retry_on_429=False,
                    )

                return TelegramResponse(
                    success=False,
                    status_code=429,
                    data=data,
                    error_message="Rate limit exceeded",
                )

            return TelegramResponse(
                success=False,
                status_code=response.status_code,
                error_message=f"HTTP {response.status_code}: {response.text}",
            )

        except httpx.TimeoutException as exc:
            logger.error(
                "Telegram request timed out (%s).",
                type(exc).__name__,
            )
            return TelegramResponse(
                success=False,
                status_code=408,
                error_message="Request Timed Out",
            )
        except Exception as exc:
            logger.error(
                "Unexpected Telegram connection error (%s): %s",
                type(exc).__name__,
                exc,
            )
            return TelegramResponse(
                success=False,
                status_code=0,
                error_message=str(exc),
            )


async def _raw_http_get_bytes(url: str) -> Optional[bytes]:
    """Download bytes from Telegram using the same IPv4-only transport."""
    try:
        async with httpx.AsyncClient(
            transport=_create_telegram_transport(),
            timeout=60.0,
            headers=HEADERS,
            trust_env=False,
        ) as client:
            response = await client.get(url)
            if response.status_code == 200:
                return response.content
            return None
    except httpx.TimeoutException as exc:
        logger.error(
            "Telegram file download timed out (%s).",
            type(exc).__name__,
        )
        return None
    except Exception as exc:
        logger.error(
            "Telegram file download failed (%s): %s",
            type(exc).__name__,
            exc,
        )
        return None


class TelegramBot:
    """Client interface for the Telegram Bot API."""

    def __init__(self, token: str):
        self.token = token

    async def send_request(
        self,
        endpoint: str,
        payload: Dict[str, Any],
        retry_on_429: bool = False,
    ) -> TelegramResponse:
        url = f"{BASE_URL}/bot{self.token}/{endpoint}"
        return await _raw_http_post(url, payload, retry_on_429)

    async def get_file_path(self, file_id: str) -> Optional[str]:
        resp = await self.send_request("getFile", {"file_id": file_id})
        if resp.success:
            return resp.data.get("result", {}).get("file_path")
        return None

    async def download_file(self, file_path: str) -> Optional[bytes]:
        url = f"{BASE_URL}/file/bot{self.token}/{file_path}"
        return await _raw_http_get_bytes(url)
