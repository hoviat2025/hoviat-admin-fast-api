# app/modules/hilfen/services/album_cache_service.py
"""
Simple in‑memory album part cache.

Stores raw Telegram updates keyed by media_group_id so that all parts of
an album can be collected within a short time window.

The interface is intentionally minimal – later it can be swapped with a
diskcache or Redis implementation by providing the same methods.
"""

from collections import defaultdict


class AlbumCacheService:
    """Thread‑safe? Not required because asyncio runs in a single thread."""

    def __init__(self):
        self._store: dict[str, list[dict]] = defaultdict(list)

    def add_part(self, media_group_id: str, update: dict) -> None:
        """Append an album part to the cache."""
        self._store[media_group_id].append(update)

    def collect(self, media_group_id: str) -> list[dict]:
        """Retrieve all parts and remove them from the cache."""
        return self._store.pop(media_group_id, [])