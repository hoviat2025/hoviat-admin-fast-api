import asyncio
import sys
import os

# 1. Setup Path to find 'app'
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 2. Import Clients (to initialize them) and the Service
from app.shared.clients.telegram import telegram_client
from app.shared.clients.storage import storage_client
from app.modules.eurobot.members.services.profile_service import save_user_profile_to_cloud

# Use a chat_id you know has a profile picture
TEST_CHAT_ID = "6385568014"

async def main():
    print(f"--- Starting Profile Upload Test for ID: {TEST_CHAT_ID} ---")

    # 3. Manually Start Clients (Simulating FastAPI Startup)
    # Telegram is Async
    await telegram_client.start()
    # Storage is Sync (Boto3)
    storage_client.start()

    try:
        # 4. Run the actual Service
        url = await save_user_profile_to_cloud(TEST_CHAT_ID)
        
        if url:
            print(f"\n✅ TEST PASSED")
            print(f"File uploaded to: {url}")
        else:
            print("\n❌ TEST FAILED")

    except Exception as e:
        print(f"\n💥 Exception occurred: {e}")

    finally:
        # 5. Manually Stop Clients (Simulating FastAPI Shutdown)
        await telegram_client.stop()
        storage_client.stop()
        print("--- Connections Closed ---")

if __name__ == "__main__":
    if TEST_CHAT_ID == "YOUR_CHAT_ID":
        print("⚠️  Please set a valid TEST_CHAT_ID in the script.")
    else:
        asyncio.run(main())