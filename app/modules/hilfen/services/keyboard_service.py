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
    ROLE_RENT_TEXT,
    ROLE_PUBLISH_TEXT,
    HOUSE_PREVIEW_CONFIRM_PREFIX,
    HOUSE_PREVIEW_DECLINE_PREFIX,
    ADMIN_CONFIRM_PREFIX,
    ADMIN_DECLINE_PREFIX,
    STOP_NEWS_PREFIX,
    PREVIEW_CONFIRM_TEXT,
    PREVIEW_DECLINE_TEXT,
    ADMIN_CONFIRM_TEXT,
    ADMIN_DECLINE_TEXT,
    VIEW_POST_TEXT,
    VIEW_MY_AD_TEXT,
    STOP_NEWS_TEXT,
)


def get_main_menu_keyboard() -> list[list[dict]]:
    return [
        [
            {"text": "🏠 خانه 🏠"},
            {"text": "💶 تبادل یورو 💶"},
            {"text": "🔖 کار و نیازمندی‌ها 💼"},
        ],
        [
            {"text": "👤 پروفایل من 👤"},
            {"text": "📁 آگهی‌های من 📁"},
            {"text": "❔ راهنما و پشتیبانی 📩"},
        ],
    ]


def build_city_keyboard(
    cities: list[str],
    cancel_message: str | None = None,
) -> list[list[dict]]:
    rows: list[list[dict]] = []
    flag = CITY_FLAG
    city_buttons = [{"text": f"{flag} {city}"} for city in cities]
    for i in range(0, len(city_buttons), 3):
        rows.append(city_buttons[i : i + 3])
    rows.append([{"text": ANOTHER_CITY_BUTTON_TEXT}])
    cancel_text = (
        f"{CANCEL_PREFIX} {cancel_message}" if cancel_message else CANCEL_PREFIX
    )
    rows.append([{"text": cancel_text}])
    return rows


def build_cancel_keyboard(
    cancel_message: str | None = None,
) -> list[list[dict]]:
    cancel_text = (
        f"{CANCEL_PREFIX} {cancel_message}" if cancel_message else CANCEL_PREFIX
    )
    return [[{"text": cancel_text}]]


def build_role_keyboard(
    cancel_message: str | None = None,
) -> list[list[dict]]:
    rows = [
        [{"text": ROLE_RENT_TEXT}],
        [{"text": ROLE_PUBLISH_TEXT}],
    ]
    cancel_text = (
        f"{CANCEL_PREFIX} {cancel_message}" if cancel_message else CANCEL_PREFIX
    )
    rows.append([{"text": cancel_text}])
    return rows


def build_photos_keyboard() -> list[list[dict]]:
    cancel_text = f"{CANCEL_PREFIX} {PHOTO_CANCEL_MESSAGE}"
    return [
        [{"text": SKIP_PHOTOS_BUTTON_TEXT}],
        [{"text": cancel_text}],
    ]


def build_preview_confirm_keyboard(news_type: str, news_id: int) -> list[list[dict]]:
    confirm_prefix = f"confirm_news_{news_type}_"
    decline_prefix = f"decline_news_{news_type}_"
    return [
        [
            {
                "text": PREVIEW_CONFIRM_TEXT,
                "callback_data": f"{confirm_prefix}{news_id}",
            },
            {
                "text": PREVIEW_DECLINE_TEXT,
                "callback_data": f"{decline_prefix}{news_id}",
            },
        ]
    ]


def build_admin_review_keyboard(news_id: int) -> list[list[dict]]:
    """
    Inline keyboard shown to the admin for confirming or declining a news.
    """
    return [
        [
            {
                "text": ADMIN_CONFIRM_TEXT,
                "callback_data": f"{ADMIN_CONFIRM_PREFIX}{news_id}",
            },
            {
                "text": ADMIN_DECLINE_TEXT,
                "callback_data": f"{ADMIN_DECLINE_PREFIX}{news_id}",
            },
        ]
    ]


def build_admin_published_keyboard(post_url: str) -> list[list[dict]]:
    """
    Inline keyboard shown to the admin after a news is published.
    Contains only a link to the post.
    """
    return [[{"text": VIEW_POST_TEXT, "url": post_url}]]


def build_user_published_keyboard(news_id: int, post_url: str) -> list[list[dict]]:
    """
    Inline keyboard shown to the user after their news is published.
    Contains a link to the post and a "Stop the news" button.
    """
    return [
        [
            {"text": VIEW_MY_AD_TEXT, "url": post_url},
            {
                "text": STOP_NEWS_TEXT,
                "callback_data": f"{STOP_NEWS_PREFIX}{news_id}",
            },
        ]
    ]


def build_user_stopped_keyboard(post_url: str) -> list[list[dict]]:
    """
    Inline keyboard shown to the user after they stop the news.
    Contains only the link to the post (no stop button).
    """
    return [[{"text": VIEW_MY_AD_TEXT, "url": post_url}]]