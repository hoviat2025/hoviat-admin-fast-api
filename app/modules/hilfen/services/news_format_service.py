# app/modules/hilfen/services/news_format_service.py
"""
Formatting helpers for news previews, admin messages, and comments.
"""

from app.models.hilfen_news import HilfenNews
from app.models.user import User

# ---------------------------------------------------------------------------
# Persian city hashtags – keyed by the Persian city names stored in DB
# ---------------------------------------------------------------------------
PERSIAN_CITY_TAGS = {
    "برلین": "#برلین",
    "هامبورگ": "#هامبورگ",
    "نورنبرگ": "#نورنبرگ",
    # add other cities as needed
}


def format_news_preview(city: str | None, news_text: str) -> str:
    """
    Build the preview text shown to the user and later to the admin.

    The format follows a fixed Persian template:
        🔵
        {description}
        
        🏙شهر:  #{city_in_persian}  آلمان

        👤 ارتباط با شخص در کامنت 👇
    """
    parts = ["🔵"]
    parts.append(news_text)
    if city:
        persian_tag = PERSIAN_CITY_TAGS.get(city, f"#{city}")
        parts.append("")  # blank line
        parts.append(f"🏙شهر:  {persian_tag}  آلمان")
    parts.append("")  # blank line
    parts.append("👤 ارتباط با شخص در کامنت 👇")
    return "\n".join(parts)


def format_decline_comment(news: HilfenNews, decline_reason: str) -> str:
    """Build the comment that will be posted in the admin group when a house ad is declined."""
    preview = format_news_preview(news.city, news.news_text or "")
    return f"⚠️ **آگهی خانه رد شد**\n{preview}\n\n**دلیل:** {decline_reason}"


def format_published_comment(news: HilfenNews) -> str:
    """
    Build the comment text that is posted in the various groups when a house ad is published.

    After admin confirmation, news.news_text holds the full (possibly edited)
    caption as it should appear.  We therefore use it directly without
    prepending the city again.
    """
    return f"🏠 **آگهی خانه جدید منتشر شد**\n{news.news_text or ''}"


def format_contact_message(user: User) -> str:
    """
    Build the contact text that is posted as a comment under the news in the discussion group.

    Uses a simple HTML <a> tag, which Telegram's parse_mode='HTML' will render
    as a clickable link.
    """
    return (
        "👤 ارتباط با آگهی‌دهنده: "
        f'<a href="tg://user?id={user.user_id}">ارسال پیام</a>'
    )


def format_stopped_news(news_text: str) -> str:
    """Build the text that replaces the original ad when the user stops it."""
    return f"⛔️ **این آگهی متوقف شده است**\n{news_text}"