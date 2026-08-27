from app.core.config import settings
from app.shared.clients.telegram import TelegramBot

# Define your bots here. 
# They are lightweight wrappers around the shared connection pool.

euro_bot = TelegramBot(token=settings.EURO_BOT_TOKEN)
sender_bot = TelegramBot(token=settings.SENDER_BOT_TOKEN)
hilfen_bot = TelegramBot(token=settings.HILFEN_BOT_TOKEN)

# SNS login bot: issues website login codes and serves as the last-resort
# getChat source for users who only started this bot (not eurobot/hilfen).
sns_login_bot = TelegramBot(token=settings.SNS_LOGIN_BOT_TOKEN)

# If you add more bots in .env later, just add them here:
# support_bot = TelegramBot(token=settings.SUPPORT_BOT_TOKEN)