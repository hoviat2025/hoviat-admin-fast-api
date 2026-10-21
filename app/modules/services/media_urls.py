"""Build public business media URLs only from managed storage keys."""

import re
from urllib.parse import urlsplit

from app.core.config import settings

_COVER_KEY = re.compile(r"business-covers/[1-9][0-9]*/[a-f0-9]{32}\.jpg\Z")


def is_managed_cover_key(key: str | None) -> bool:
    return isinstance(key, str) and _COVER_KEY.fullmatch(key) is not None


def service_media_base() -> str | None:
    base = (settings.SERVICE_MEDIA_URL or settings.PROFILE_MEDIA_URL or "").strip().rstrip("/")
    try:
        parsed = urlsplit(base)
        parsed.port  # Reject malformed ports as well as malformed URLs.
        if (
            parsed.scheme in {"http", "https"}
            and parsed.hostname
            and parsed.username is None
            and parsed.password is None
            and not parsed.query
            and not parsed.fragment
        ):
            return base
    except ValueError:
        pass
    return None


def public_cover_image_url(key: str | None) -> str | None:
    base = service_media_base()
    return f"{base}/{key}" if base and is_managed_cover_key(key) else None
