"""Validate a user-supplied map link without fetching or rewriting it."""
from urllib.parse import urlsplit

from app.core.exceptions import ServiceError


def clean_google_maps_url(value):
    if value is None or not value.strip():
        return None
    value = value.strip()
    try:
        url = urlsplit(value)
        host = (url.hostname or "").lower()
        valid = (
            url.scheme == "https" and not url.username and not url.password
            and url.port in (None, 443) and not any(ord(c) < 32 for c in value)
            and (
                host == "maps.app.goo.gl"
                or (host == "goo.gl" and url.path.startswith("/maps/"))
                or (host in {"google.com", "www.google.com", "maps.google.com",
                             "google.de", "www.google.de", "maps.google.de"}
                    and (url.path == "/maps" or url.path.startswith("/maps/")
                         or host.startswith("maps.")))
            )
        )
    except (ValueError, AttributeError):
        valid = False
    if not valid:
        raise ServiceError("INVALID_INPUT", "Use an HTTPS Google Maps link (including maps.app.goo.gl)", 422)
    return value
