import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.modules.eurobot.members.services.profile_service import save_user_profile_to_cloud

# Use a chat_id you know has a profile picture
TEST_CHAT_ID = "6385568014"

if __name__ == "__main__":
    if TEST_CHAT_ID == "YOUR_CHAT_ID":
        print("Set your ID first")
    else:
        asyncio.run(save_user_profile_to_cloud(TEST_CHAT_ID))