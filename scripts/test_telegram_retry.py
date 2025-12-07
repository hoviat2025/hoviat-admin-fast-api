import asyncio
import sys
import os

# Add the root directory to path so we can import 'app'
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.shared.clients.telegram import TelegramClient
from app.core.config import settings

# --- CONFIGURATION ---
# Replace this with your actual Chat ID or Channel Username (e.g., "@my_channel")
TEST_CHAT_ID = "-1003307384504" 
# ---------------------

async def main():
    print(f"--- Starting Flood Test on {settings.TELEGRAM_BASE_URL} ---")
    
    client = TelegramClient()
    tasks = []
    
    # We send 25 messages rapidly to trigger the 429
    for i in range(1, 25):
        payload = {
            "chat_id": TEST_CHAT_ID,
            "text": f"Flood test message #{i}"
        }
        tasks.append(send_and_report(client, i, payload))

    await asyncio.gather(*tasks)

async def send_and_report(client, index, payload):
    print(f"Sending Request #{index}...")
    try:
        # returns a TelegramResponse object now
        result = await client.send_request("sendMessage", payload, retry_on_429=True)
        
        # --- UPDATED LOGIC HERE ---
        if result.success:
            # We access .data instead of the object itself
            msg_id = result.data.get("result", {}).get("message_id")
            print(f"✅ Request #{index} Success: ID {msg_id}")
        else:
            # We print the error message from the object
            print(f"❌ Request #{index} Failed: Code {result.status_code} | Reason: {result.error_message}")
            
    except Exception as e:
        print(f"💥 Request #{index} Exception: {e}")

if __name__ == "__main__":
    if TEST_CHAT_ID == "YOUR_CHAT_ID_HERE":
        print("⚠️  PLEASE SET 'TEST_CHAT_ID' INSIDE THE SCRIPT BEFORE RUNNING ⚠️")
    else:
        asyncio.run(main())