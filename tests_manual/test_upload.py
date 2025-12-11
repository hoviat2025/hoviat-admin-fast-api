import asyncio
from app.shared.clients.telegram import telegram_system
from app.shared.clients.storage import storage_client
from app.modules.eurobot.members.services.profile_service import save_user_profile_to_cloud

# CONFIG: Use a user ID that definitely has a profile pic
TEST_USER_ID = 6385568014

async def main():
    print(f"--- ☁️ Starting Profile Upload Test ---")

    # 1. Manually Start Infrastructure
    # We need the system running so the bot instance can connect
    await telegram_system.start()
    storage_client.start()

    try:
        # 2. Call the service
        # Since we added try/except inside the function, this won't crash even if it fails
        result = await save_user_profile_to_cloud(TEST_USER_ID)
        
        if result:
            print(f"\n✅ TEST PASSED")
            print(f"Full URL:  {result['image_url']}")
            print(f"Path only: {result['image_path']}")
        else:
            print("\n❌ TEST FAILED (Returned False)")

    except Exception as e:
        # This catch is just for the test script itself
        print(f"💥 Exception in Test Script: {e}")

    finally:
        # 3. Cleanup
        await telegram_system.stop()
        storage_client.stop()

if __name__ == "__main__":
    asyncio.run(main())