# app/modules/hilfen/services/city_service.py
"""
City service for the Hilfen bot.

Provides the master list of German cities (in Persian) and a helper to validate a city name.
All city-related UI elements should obtain the list from here.
"""

# Source of truth for valid German cities – stored in Persian
_GERMAN_CITIES = [
    "برلین",
    "هامبورگ",
    "نورنبرگ",
    "دورتموند",
    "مونیخ",
    "کلن",
    "فرانکفورت",
    "اشتوتگارت",
    "درسدن",
    "آخن",
    "هانوفر",
    "برمن",
    "دوسلدورف",
    "اسن",
    "لایپزیگ"
]



def get_all_cities() -> list[str]:
    """Return the authoritative list of valid German cities (Persian names)."""
    return _GERMAN_CITIES.copy()


def is_valid_city(city_name: str) -> bool:
    """Check if a city name is in the list (case‑sensitive)."""
    return city_name in _GERMAN_CITIES