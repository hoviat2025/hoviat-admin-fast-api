import asyncio
from app.shared.clients.telegram import telegram_system
from app.shared.clients.storage import storage_client
from app.modules.eurobot.members.services.profile_service import save_user_profile_to_cloud

# CONFIG: Use a user ID that definitely has a profile pic
TEST_USER_ID = "6385568014" 

async def main():
    print(f"--- ☁️ Starting Profile Upload Test ---")

    # 1. Manually Start Infrastructure
    await telegram_system.start()
    storage_client.start()

    try:
        # 2. Call the service (which uses euro_bot internally)
        url = await save_user_profile_to_cloud(TEST_USER_ID)
        
        if url:
            print(f"\n✅ TEST PASSED")
            print(f"Profile URL: {url}")
        else:
            print("\n❌ TEST FAILED")

    except Exception as e:
        print(f"💥 Exception: {e}")

    finally:
        # 3. Cleanup
        await telegram_system.stop()
        storage_client.stop()

if __name__ == "__main__":
    asyncio.run(main())