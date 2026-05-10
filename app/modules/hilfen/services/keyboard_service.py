# app/modules/hilfen/services/keyboard_service.py
"""
Keyboard factory for the Hilfen bot.

All reusable keyboards are defined here as pure functions so handlers and
other services can obtain a keyboard without repeating its layout.
"""

from app.modules.hilfen.constants import (
    CANCEL_PREFIX,
    BACK_BUTTON_TEXT,
    ANOTHER_CITY_BUTTON_TEXT,
    CITY_FLAG,
)


def get_main_menu_keyboard() -> list[list[dict]]:
    """
    Return the main menu keyboard that is shown after registration is complete.

    Layout:
        [ house ]  [ work and needs ]  [ euro ]
        [ my profile ]  [ my ads ]  [ help ]
    """
    return [
        [
            {"text": "🏠 House 🏠"},
            {"text": "💶 Euro Exchange 💶"},
            {"text": "🔖 Work and Needs 💼"},
        ],
        [
            {"text": "👤 My Profile 👤"},
            {"text": "📁 My Ads 📁"},
            {"text": "❔ Help and Support 📩"},
        ],
    ]


def build_city_keyboard(
    cities: list[str],
    cancel_message: str | None = None,
) -> list[list[dict]]:
    """
    Build a reply keyboard for city selection.

    - Each city is prefixed with the German flag (e.g. "🇩🇪 Berlin").
    - Cities are laid out in rows of 3 columns.
    - An "Another City" button is placed on its own row.
    - A "Back" button on its own row.
    - A cancel button on the last row. If *cancel_message* is given,
      the button text becomes ``f"{CANCEL_PREFIX} {cancel_message}"``,
      otherwise it is just ``CANCEL_PREFIX``.
    """
    rows: list[list[dict]] = []

    # City buttons – rows of 3
    flag = CITY_FLAG
    city_buttons = [{"text": f"{flag} {city}"} for city in cities]
    for i in range(0, len(city_buttons), 3):
        rows.append(city_buttons[i : i + 3])

    # "Another City" row
    rows.append([{"text": ANOTHER_CITY_BUTTON_TEXT}])

    # "Back" row
    rows.append([{"text": BACK_BUTTON_TEXT}])

    # Cancel row
    cancel_text = (
        f"{CANCEL_PREFIX} {cancel_message}" if cancel_message else CANCEL_PREFIX
    )
    rows.append([{"text": cancel_text}])

    return rows


def build_cancel_back_keyboard(
    cancel_message: str | None = None,
) -> list[list[dict]]:
    """
    Minimal keyboard with only Cancel and Back buttons.

    Used when the user needs to send free‑form text but should be able
    to abort or go back.
    """
    cancel_text = (
        f"{CANCEL_PREFIX} {cancel_message}" if cancel_message else CANCEL_PREFIX
    )
    return [
        [{"text": cancel_text}],
        [{"text": BACK_BUTTON_TEXT}],
    ]