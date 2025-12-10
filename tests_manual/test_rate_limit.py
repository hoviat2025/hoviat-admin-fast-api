import asyncio
from app.core.config import settings
from app.shared.clients.telegram import telegram_system
from app.shared.bot_instances import sender_bot # Using Sender Bot

# CONFIG
TEST_CHAT_ID = "-1003307384504" 

async def main():
    print(f"--- 🌊 Starting Rate Limit Test (Sender Bot) ---")
    
    # 1. Start the Shared Engine
    await telegram_system.start()

    tasks = []
    # Send 25 messages fast
    for i in range(1, 25):
        payload = {
            "chat_id": TEST_CHAT_ID,
            "text": f"Flood test message #{i}"
        }
        tasks.append(send_wrap(i, payload))

    try:
        await asyncio.gather(*tasks)
    finally:
        await telegram_system.stop()

async def send_wrap(index, payload):
    print(f"Sending #{index}...")
    # retry_on_429=True will handle the waiting automatically
    res = await sender_bot.send_request("sendMessage", payload, retry_on_429=True)
    
    if res.success:
        print(f"✅ #{index} Success (ID: {res.data['result']['message_id']})")
    else:
        print(f"❌ #{index} Failed: {res.error_message}")

if __name__ == "__main__":
    asyncio.run(main())