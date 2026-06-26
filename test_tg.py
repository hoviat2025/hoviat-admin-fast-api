# test_tg.py
import asyncio
import httpx

BOT_TOKEN = "8640215751:AAHcOwwGNqSSr0RwZqw4eEC7DaBMyP3OsFs"
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

# Replace this with your actual MAIN_CHANNEL_ID from your .env
TEST_CHANNEL_ID = -1003941932759  

async def run_diagnostics():
    async with httpx.AsyncClient(timeout=30.0) as client:
        print("--- Diagnostic 1: Testing getMe (Basic connectivity) ---")
        try:
            resp = await client.get(f"{BASE_URL}/getMe")
            print(f"Success! Status: {resp.status_code}")
            print(f"Bot Info: {resp.json()}\n")
        except Exception as e:
            print(f"Failed getMe: {e}\n")

        print("--- Diagnostic 2: Testing sendMessage (Plain Text to Channel) ---")
        try:
            payload = {
                "chat_id": TEST_CHANNEL_ID,
                "text": "🔌 Diagnostics: Text connection test."
            }
            resp = await client.post(f"{BASE_URL}/sendMessage", json=payload)
            print(f"Status: {resp.status_code}")
            print(f"Response: {resp.json()}\n")
        except Exception as e:
            print(f"Failed sendMessage: {e}\n")

        print("--- Diagnostic 3: Testing sendPhoto (URL Photo to Channel) ---")
        try:
            # We will try sending the Vecteezy fallback image
            url_img = "https://static.vecteezy.com/system/resources/previews/036/280/651/non_2x/default-avatar-profile-icon-social-media-user-image-gray-avatar-icon-blank-profile-silhouette-illustration-vector.jpg"
            payload = {
                "chat_id": TEST_CHANNEL_ID,
                "photo": url_img,
                "caption": "🔌 Diagnostics: URL image connection test."
            }
            resp = await client.post(f"{BASE_URL}/sendPhoto", json=payload)
            print(f"Status: {resp.status_code}")
            print(f"Response: {resp.json()}\n")
        except Exception as e:
            print(f"Failed sendPhoto (URL): {e}\n")

if __name__ == "__main__":
    asyncio.run(run_diagnostics())