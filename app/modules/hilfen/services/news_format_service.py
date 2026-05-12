# app/modules/hilfen/services/news_format_service.py
"""
Formatting helpers for news previews, admin messages, and comments.
"""

from app.models.hilfen_news import HilfenNews


def format_news_preview(city: str | None, news_text: str) -> str:
    """
    Build the preview text shown to the user and later to the admin.
    For now it simply returns the news_text with an optional city prefix.
    """
    parts = []
    if city:
        parts.append(f"📍 {city}")
    parts.append(news_text)
    return "\n".join(parts)


def format_decline_comment(news: HilfenNews, decline_reason: str) -> str:
    """
    Build the comment that will be posted in the admin group when a
    house ad is declined by an admin.
    """
    preview = format_news_preview(news.city, news.news_text or "")
    return f"⚠️ **House ad declined**\n{preview}\n\n**Reason:** {decline_reason}"