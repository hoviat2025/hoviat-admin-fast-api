# app/modules/hilfen/constants.py
"""
Central constants for the Hilfen bot.

All texts that appear on keyboards and are later matched in handlers
must be defined here so they stay in sync.
"""

# Cancel button – always starts with this prefix.
# If a cancel_message is supplied, the full label becomes: "{CANCEL_PREFIX} {cancel_message}"
CANCEL_PREFIX = "❌ Cancel"

# Back button
BACK_BUTTON_TEXT = "🔙 Back"

# Another City button in city selection
ANOTHER_CITY_BUTTON_TEXT = "📍 Another City"

# German flag emoji prepended to each city button
CITY_FLAG = "🇩🇪"

# House photo step
SKIP_PHOTOS_BUTTON_TEXT = "🚫 I won't send photos"
PHOTO_CANCEL_MESSAGE = "Cancelling the news"

# Inline callbacks
CONFIRM_CALLBACK_PREFIX = "confirm_news_house_"
DECLINE_CALLBACK_PREFIX = "decline_news_house_"

# Admin check channel (placeholder, later configurable)
ADMIN_CHECK_CHANNEL_ID = -1001234567890   # <<< REPLACE with real channel id