"""Shared write policy for user data received from the Telegram bots."""

from typing import Any, Mapping


PROTECTED_FROM_NULL_FIELDS = frozenset(
    {
        # Identity / contact fields: an empty value from a bot client means
        # "I did not provide this", NEVER "wipe the existing value". Clients
        # must adopt field-level timestamp reconciliation before they may
        # legitimately clear these.
        "first_name",
        "last_name",
        "phone_number",
        "whatsapp_number",
        "country",
        "is_ban",
        "ban_time",
        "join_date",
        # Hilfen identity fields: same rule as above. A client sending
        # hilfen_id/date_join empty must not silently erase the stored value.
        "hilfen_id",
        "hilfen_date_join",
    }
)


def omit_protected_nulls(data: Mapping[str, Any]) -> dict[str, Any]:
    """Return bot data without assignments that would null protected fields.

    This intentionally checks for ``None`` rather than truthiness so valid values
    such as ``False``, ``0``, and empty strings are preserved.
    """

    return {
        field: value
        for field, value in data.items()
        if not (field in PROTECTED_FROM_NULL_FIELDS and value is None)
    }
