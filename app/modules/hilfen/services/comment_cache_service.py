# app/modules/hilfen/services/comment_cache_service.py
"""
In‑memory cache that maps a channel post to its automatically‑forwarded
comment in the linked discussion group.

Works similarly to AlbumCacheService – one global instance is shared by
the comment‑catching handler and the admin confirm flow.
"""


class CommentMappingCache:
    """
    Stores mappings:
      key   = (channel_id, original_message_id)
      value = (group_chat_id, group_message_id)
    """

    def __init__(self):
        self._store: dict[tuple[int, int], tuple[int, int]] = {}

    def add_mapping(
        self,
        channel_id: int,
        original_message_id: int,
        group_chat_id: int,
        group_message_id: int,
    ) -> None:
        self._store[(channel_id, original_message_id)] = (
            group_chat_id,
            group_message_id,
        )

    def get_mapping(
        self, channel_id: int, original_message_id: int
    ) -> tuple[int, int] | None:
        return self._store.get((channel_id, original_message_id))


# Singleton – shared across the whole bot process
comment_mapping_cache = CommentMappingCache()