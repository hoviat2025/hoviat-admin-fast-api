import asyncio
from app.shared.clients.telegram import telegram_system
from app.shared.bot_instances import euro_bot, sender_bot

# CONFIG
TEST_CHAT_ID = "-1003307384504"

async def main():
    print(f"--- 🤖 Multi-Bot Simultaneous Test ---")
    
    # 1. Start Engine (Connects to Telegram API)
    await telegram_system.start()

    try:
        # 2. Define the tasks
        task1 = euro_bot.send_request("sendMessage", {
            "chat_id": TEST_CHAT_ID, 
            "text": "🇪🇺 Hello from Euro Bot!"
        })
        
        task2 = sender_bot.send_request("sendMessage", {
            "chat_id": TEST_CHAT_ID, 
            "text": "📨 Hello from Sender Bot!"
        })

        # 3. Execute exactly at the same time
        print("Sending both messages now...")
        results = await asyncio.gather(task1, task2)
        
        # 4. Analyze
        euro_res, sender_res = results
        
        if euro_res.success:
            print(f"✅ EuroBot Sent (ID: {euro_res.data['result']['message_id']})")
        else:
            print(f"❌ EuroBot Failed: {euro_res.error_message}")

        if sender_res.success:
            print(f"✅ SenderBot Sent (ID: {sender_res.data['result']['message_id']})")
        else:
            print(f"❌ SenderBot Failed: {sender_res.error_message}")

    finally:
        await telegram_system.stop()

if __name__ == "__main__":
    asyncio.run(main())