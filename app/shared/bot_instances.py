from app.core.config import settings
from app.shared.clients.telegram import TelegramBot

# Define your bots here. 
# They are lightweight wrappers around the shared connection pool.

euro_bot = TelegramBot(token=settings.EURO_BOT_TOKEN)
sender_bot = TelegramBot(token=settings.SENDER_BOT_TOKEN)
hilfen_bot = TelegramBot(token=settings.HILFEN_BOT_TOKEN)

# If you add more bots in .env later, just add them here:
# support_bot = TelegramBot(token=settings.SUPPORT_BOT_TOKEN)