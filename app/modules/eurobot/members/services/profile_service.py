# 1. CHANGE THIS IMPORT
# Old: from app.shared.clients.telegram import telegram_client
# New: Import the specific bot instance defined in shared/bot_instances.py
from app.shared.bot_instances import euro_bot 
from app.shared.clients.storage import storage_client
import uuid

async def save_user_profile_to_cloud(chat_id: int):
    # 2. CHANGE ALL USAGES from 'telegram_client' to 'euro_bot'
    
    # 1. Get Chat Info
    chat_resp = await euro_bot.send_request("getChat", {"chat_id": chat_id})
    
    if not chat_resp.success:
        print(f"Could not get chat info: {chat_resp.error_message}")
        return False

    # 2. Extract File ID
    photo_obj = chat_resp.data.get("result", {}).get("photo")
    
    if not photo_obj:
        print("User has no profile photo.")
        return False
        
    file_id = photo_obj.get("big_file_id")

    # 3. Get File Path
    file_path = await euro_bot.get_file_path(file_id)
    if not file_path:
        print("Could not retrieve file path from Telegram.")
        return False

    # 4. Download Binary
    image_bytes = await euro_bot.download_file(file_path)
    if not image_bytes:
        print("Download failed.")
        return False

    # 5. Upload to R2
    file_extension = file_path.split(".")[-1]
    filename = f"{chat_id}_{uuid.uuid4()}.{file_extension}"
    
    public_url = await storage_client.upload_file(image_bytes, filename)
    
    if public_url:
        print(f"✅ Success! Image saved at: {public_url}")
        return public_url
    else:
        print("❌ Upload to R2 failed.")
        return False