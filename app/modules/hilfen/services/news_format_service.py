# app/modules/hilfen/services/news_format_service.py
"""
Formatting helpers for news previews and final posts.
"""


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