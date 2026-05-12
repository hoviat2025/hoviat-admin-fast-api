# app/modules/hilfen/services/channel_mapping_service.py
"""
Resolves the Telegram channel ID where a particular news should be published.
"""

# ---------------------------------------------------------------------------
# Hard‑coded mapping – replace with DB or config later.
# ``another_city`` is used for any city not explicitly listed.
# ---------------------------------------------------------------------------




#berlin group id 3960617305

#berlin channel id 3960248207


_HOUSE_CHANNELS: dict[str, int] = {
    "berlin": -1003960248207,
    "dortmund": -1001234567891,
    "another_city": -1001234567892,
}


def get_house_channel(city: str | None) -> int | None:
    """
    Return the channel ID for the **house** news in the given city.
    If the city is unknown (custom), fall back to 'another_city'.
    Returns None when no fallback is defined.
    """
    if not city:
        return None
    city_lower = city.strip().lower()
    return _HOUSE_CHANNELS.get(city_lower, _HOUSE_CHANNELS.get("another_city"))