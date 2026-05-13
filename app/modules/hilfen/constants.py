# app/modules/hilfen/constants.py
"""
Central constants for the Hilfen bot.

All texts that appear on keyboards and are later matched in handlers
must be defined here so they stay in sync.
"""

# Cancel button – always starts with this prefix.
# If a cancel_message is supplied, the full label becomes: "{CANCEL_PREFIX} {cancel_message}"
CANCEL_PREFIX = "❌ لغو"

# Back button
BACK_BUTTON_TEXT = "🔙 بازگشت"

# Another City button in city selection
ANOTHER_CITY_BUTTON_TEXT = "📍 شهر دیگر"

# German flag emoji prepended to each city button
CITY_FLAG = "🇩🇪"

# House photo step
SKIP_PHOTOS_BUTTON_TEXT = "🚫 عکس نمی‌فرستم"
PHOTO_CANCEL_MESSAGE = "انصراف از آگهی"

# Inline callbacks for house preview confirm/decline
HOUSE_PREVIEW_CONFIRM_PREFIX = "confirm_news_house_"
HOUSE_PREVIEW_DECLINE_PREFIX = "decline_news_house_"

# House role selection step (rent vs. publish)
ROLE_RENT_TEXT = "🏠 می‌خواهم اجاره کنم"
ROLE_PUBLISH_TEXT = "🏠 می‌خواهم برای اجاره آگهی کنم"

# Admin review inline callbacks (used in check_admin_channel)
ADMIN_CONFIRM_PREFIX = "admin_confirm_house_"
ADMIN_DECLINE_PREFIX = "admin_decline_house_"

# Stop house news (user action)
STOP_NEWS_PREFIX = "stop_news_house_"

# ---------------------------------------------------------------------------
# Reusable button texts for various keyboards
# ---------------------------------------------------------------------------
PREVIEW_CONFIRM_TEXT = "✅ تایید"
PREVIEW_DECLINE_TEXT = "❌ انصراف"
ADMIN_CONFIRM_TEXT = "✅ تایید"
ADMIN_DECLINE_TEXT = "❌ رد"
VIEW_POST_TEXT = "🔗 مشاهده پست"
VIEW_MY_AD_TEXT = "🔗 مشاهده آگهی من"
STOP_NEWS_TEXT = "⏹ توقف آگهی"