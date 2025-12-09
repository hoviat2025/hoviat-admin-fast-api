Here is the clean `README.md` content. You can copy and paste this directly into **`app/shared/clients/README.md`**.

```markdown
# Shared Infrastructure Clients

This directory contains the singleton clients used to communicate with external services (Telegram and Cloudflare R2/S3).

## ⚠️ Important Usage Rule

These clients follow the **Singleton Pattern** to maintain persistent connections and optimize performance.

*   ❌ **DO NOT** instantiate classes manually (e.g., `client = TelegramClient()`).
*   ✅ **DO** import the global instances.

```python
# Correct Import
from app.shared.clients.telegram import telegram_client
from app.shared.clients.storage import storage_client
```

---

## 📱 Telegram Client

Handles communication with the Telegram Bot API using `httpx` (Async). It includes automatic connection pooling and rate-limit handling.

### Configuration (`.env`)
```env
TELEGRAM_BOT_TOKEN=your_token
TELEGRAM_BASE_URL=https://api.telegram.org
```

### Usage Example

```python
from app.shared.clients.telegram import telegram_client

async def send_notification(chat_id: int):
    # 1. Send a Message
    # retry_on_429=True will automatically sleep if Telegram sends a "Too Many Requests" error
    response = await telegram_client.send_request(
        endpoint="sendMessage", 
        payload={"chat_id": chat_id, "text": "Hello!"}, 
        retry_on_429=True
    )

    if response.success:
        print(f"Sent! Message ID: {response.data['result']['message_id']}")
    else:
        print(f"Error: {response.error_message}")

async def get_user_photo(file_id: str):
    # 2. Download a File
    # Convert file_id to path
    path = await telegram_client.get_file_path(file_id)
    
    if path:
        # Download raw bytes
        file_bytes = await telegram_client.download_file(path)
        return file_bytes
```

---

## ☁️ Storage Client (R2 / S3)

Handles file uploads to Cloudflare R2 (or AWS S3) using `boto3`.
Although `boto3` is synchronous, this client wraps uploads in a thread pool to ensure it is **non-blocking** for FastAPI.

### Configuration (`.env`)
```env
R2_ENDPOINT_URL=https://<account_id>.r2.cloudflarestorage.com
R2_ACCESS_KEY_ID=your_access_key
R2_SECRET_ACCESS_KEY=your_secret_key
R2_BUCKET_NAME=your_bucket_name
```

### Usage Example

```python
from app.shared.clients.storage import storage_client

async def upload_image(image_data: bytes, user_id: int):
    filename = f"avatars/{user_id}.jpg"
    
    # Returns the public URL string if successful, or None if failed
    public_url = await storage_client.upload_file(
        file_bytes=image_data, 
        file_name=filename, 
        content_type="image/jpeg"
    )

    if public_url:
        print(f"File accessible at: {public_url}")
```

---

## 🛠 Using in Scripts

The clients are automatically started when the FastAPI app runs (`main.py`).
If you are writing a standalone script (e.g., inside `scripts/`), you must manually start and stop them.

```python
import asyncio
from app.shared.clients.telegram import telegram_client
from app.shared.clients.storage import storage_client

async def main():
    # 1. Start Connections
    await telegram_client.start()
    storage_client.start()

    # ... do work ...

    # 2. Close Connections
    await telegram_client.stop()
    storage_client.stop()

if __name__ == "__main__":
    asyncio.run(main())
```
```