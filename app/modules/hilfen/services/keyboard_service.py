# app/modules/hilfen/services/keyboard_service.py
"""
Keyboard factory for the Hilfen bot.

All reusable keyboards are defined here as pure functions so handlers and
other services can obtain a keyboard without repeating its layout.
"""

from app.modules.hilfen.constants import (
    CANCEL_PREFIX,
    ANOTHER_CITY_BUTTON_TEXT,
    CITY_FLAG,
    SKIP_PHOTOS_BUTTON_TEXT,
    PHOTO_CANCEL_MESSAGE,
    CONFIRM_CALLBACK_PREFIX,
    DECLINE_CALLBACK_PREFIX,
)


def get_main_menu_keyboard() -> list[list[dict]]:
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
    City selection keyboard.
    - Cities are prefixed with 🇩🇪 and arranged in rows of 3.
    - An "Another City" button on its own row.
    - A Cancel button (with optional message) on the last row.
    """
    rows: list[list[dict]] = []

    # City buttons – rows of 3
    flag = CITY_FLAG
    city_buttons = [{"text": f"{flag} {city}"} for city in cities]
    for i in range(0, len(city_buttons), 3):
        rows.append(city_buttons[i : i + 3])

    # "Another City" row
    rows.append([{"text": ANOTHER_CITY_BUTTON_TEXT}])

    # Cancel row
    cancel_text = (
        f"{CANCEL_PREFIX} {cancel_message}" if cancel_message else CANCEL_PREFIX
    )
    rows.append([{"text": cancel_text}])

    return rows


def build_cancel_keyboard(
    cancel_message: str | None = None,
) -> list[list[dict]]:
    """
    A minimal keyboard with only a Cancel button (with optional message).
    Used when the user is expected to type free‑form text.
    """
    cancel_text = (
        f"{CANCEL_PREFIX} {cancel_message}" if cancel_message else CANCEL_PREFIX
    )
    return [[{"text": cancel_text}]]


def build_photos_keyboard() -> list[list[dict]]:
    """
    Keyboard shown during the photo‑upload step:
    - "I won't send photos" button.
    - Cancel button with a fixed message.
    """
    cancel_text = f"{CANCEL_PREFIX} {PHOTO_CANCEL_MESSAGE}"
    return [
        [{"text": SKIP_PHOTOS_BUTTON_TEXT}],
        [{"text": cancel_text}],
    ]


def build_preview_confirm_keyboard(news_id: int) -> list[list[dict]]:
    """
    Inline keyboard for the user to confirm or decline the preview.
    Callback data contains the news_id so the handler can verify it.
    """
    return [
        [
            {
                "text": "✅ Confirm",
                "callback_data": f"{CONFIRM_CALLBACK_PREFIX}{news_id}",
            },
            {
                "text": "❌ Decline",
                "callback_data": f"{DECLINE_CALLBACK_PREFIX}{news_id}",
            },
        ]
    ]