
```markdown
# Shared Infrastructure Clients

This directory contains the clients used to communicate with external services (Telegram and Cloudflare R2/S3).

## 🚀 Architecture Overview

### Telegram (Multi-Tenant)
We use a **Split Architecture** to handle multiple bots efficiently:
1.  **`TelegramSystem` (`telegram_system`)**: The underlying engine. It manages a **single** shared HTTP connection pool to Telegram's API. It handles the networking and rate limits.
2.  **`TelegramBot` Instances**: Lightweight wrappers defined in `app/shared/bot_instances.py`. They hold the specific token and use the System to send messages.

### Storage (R2/S3)
We use a singleton `storage_client` that wraps `boto3` in a thread pool to ensure non-blocking async file uploads.

---

## ⚠️ Usage Rules

*   ❌ **DO NOT** instantiate `TelegramClient` or `TelegramSystem` manually in services.
*   ✅ **DO** import specific bots from `app/shared/bot_instances.py`.
*   ✅ **DO** import `storage_client` from `app/shared/clients/storage.py`.

```python
# ✅ CORRECT IMPORTS
from app.shared.bot_instances import euro_bot, sender_bot
from app.shared.clients.storage import storage_client
```

---

## 📱 Telegram Usage

### 1. Configuration
Define your tokens in `.env` and `app/core/config.py`.
Then, define the instances in `app/shared/bot_instances.py`:

```python
# app/shared/bot_instances.py
from app.shared.clients.telegram import TelegramBot
from app.core.config import settings

euro_bot = TelegramBot(token=settings.EURO_BOT_TOKEN)
sender_bot = TelegramBot(token=settings.SENDER_BOT_TOKEN)
```

### 2. Sending Messages (Service Layer)

```python
from app.shared.bot_instances import euro_bot

async def send_welcome(chat_id: int):
    # retry_on_429=True automatically handles Telegram's rate limits
    response = await euro_bot.send_request(
        endpoint="sendMessage",
        payload={"chat_id": chat_id, "text": "Hello form EuroBot!"}, 
        retry_on_429=True
    )

    if response.success:
        print(f"Sent! ID: {response.data['result']['message_id']}")
    else:
        print(f"Error: {response.error_message}")
```

### 3. Downloading Files

```python
async def save_photo(file_id: str):
    # 1. Get the remote path
    path = await euro_bot.get_file_path(file_id)
    
    if path:
        # 2. Download bytes using the shared connection pool
        file_bytes = await euro_bot.download_file(path)
        return file_bytes
```

---

## ☁️ Storage Client (R2 / S3)

Handles file uploads to Cloudflare R2. Even though the underlying library (`boto3`) is synchronous, this client runs uploads in a separate thread so it **never blocks** the FastAPI main loop.

### Usage Example

```python
from app.shared.clients.storage import storage_client

async def upload_avatar(image_bytes: bytes, user_id: int):
    filename = f"avatars/{user_id}.jpg"
    
    # Returns public URL string or None
    public_url = await storage_client.upload_file(
        file_bytes=image_bytes, 
        file_name=filename, 
        content_type="image/jpeg"
    )

    if public_url:
        print(f"Uploaded to: {public_url}")
```

---

## 🛠 Manual Scripts & Testing

If you run code **outside** of `main.py` (like in `tests_manual/` or `scripts/`), the automatic connection startup won't happen. You must manually start and stop the **System**.

```python
import asyncio
from app.shared.clients.telegram import telegram_system # Import the SYSTEM
from app.shared.clients.storage import storage_client
from app.shared.bot_instances import euro_bot # Import the BOT

async def main():
    print("--- Starting Manual Script ---")

    # 1. Start the Infrastructure
    await telegram_system.start() # Opens HTTP connection pool
    storage_client.start()        # Sets up Boto3

    try:
        # 2. Do work using the Bot Instance
        await euro_bot.send_request("sendMessage", {...})
        
    finally:
        # 3. Clean Shutdown
        await telegram_system.stop()
        storage_client.stop()

if __name__ == "__main__":
    asyncio.run(main())
```
```