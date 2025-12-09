import asyncio
import sys
import os

# Add the root directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the INSTANCE, not the Class
from app.shared.clients.telegram import telegram_client
from app.core.config import settings

TEST_CHAT_ID = "-1003307384504" 

async def main():
    print(f"--- Starting Flood Test on {settings.TELEGRAM_BASE_URL} ---")
    
    # 1. MANUALLY START THE CLIENT (Simulating app startup)
    await telegram_client.start()
    
    tasks = []
    
    try:
        # We send 25 messages rapidly
        for i in range(1, 25):
            payload = {
                "chat_id": TEST_CHAT_ID,
                "text": f"Flood test message #{i}"
            }
            # Pass the global client to the helper
            tasks.append(send_and_report(telegram_client, i, payload))

        await asyncio.gather(*tasks)
        
    finally:
        # 2. MANUALLY STOP THE CLIENT (Simulating app shutdown)
        await telegram_client.stop()
        print("--- Test Finished & Connection Closed ---")

async def send_and_report(client, index, payload):
    print(f"Sending Request #{index}...")
    try:
        result = await client.send_request("sendMessage", payload, retry_on_429=True)
        
        if result.success:
            msg_id = result.data.get("result", {}).get("message_id")
            print(f"✅ Request #{index} Success: ID {msg_id}")
        else:
            print(f"❌ Request #{index} Failed: Code {result.status_code} | Reason: {result.error_message}")
            
    except Exception as e:
        print(f"💥 Request #{index} Exception: {e}")

if __name__ == "__main__":
    if TEST_CHAT_ID == "YOUR_CHAT_ID_HERE":
        print("⚠️  PLEASE SET 'TEST_CHAT_ID' INSIDE THE SCRIPT BEFORE RUNNING ⚠️")
    else:
        asyncio.run(main())