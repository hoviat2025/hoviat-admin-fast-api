# app/modules/hilfen/services/news_format_service.py
"""
Formatting helpers for news previews, admin messages, and comments.
"""

from app.models.hilfen_news import HilfenNews
from app.models.user import User

# ---------------------------------------------------------------------------
# Temporary mapping – move to city_service when the list grows
# ---------------------------------------------------------------------------
PERSIAN_CITY_TAGS = {
    "Berlin": "#برلین",
    "Hamburg": "#هامبورگ",
    "Munich": "#مونیخ",
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
    return f"⚠️ **House ad declined**\n{preview}\n\n**Reason:** {decline_reason}"


def format_published_comment(news: HilfenNews) -> str:
    """
    Build the comment text that is posted in the various groups when a house ad is published.

    After admin confirmation, news.news_text holds the full (possibly edited)
    caption as it should appear.  We therefore use it directly without
    prepending the city again.
    """
    return f"🏠 **New house ad published**\n{news.news_text or ''}"


def format_contact_message(user: User) -> str:
    """Build the contact text that is posted as a comment under the news in the discussion group."""
    return f"📞 Contact: [Open chat](tg://user?id={user.user_id})"


def format_stopped_news(news_text: str) -> str:
    """Build the text that replaces the original ad when the user stops it."""
    return f"⛔️ **This ad has been stopped**\n{news_text}"