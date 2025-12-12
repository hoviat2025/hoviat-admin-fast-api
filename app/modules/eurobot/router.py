from fastapi import APIRouter, Depends

# 1. Import Dependency
from app.modules.eurobot.dependencies import verify_bot_token

# 2. Import Sub-Routers
from app.modules.eurobot.members.router import router as members_router
from app.modules.eurobot.channels.router import router as channels_router 
from app.modules.eurobot.channels.router import telegram_webhook_router as channels_webhook_router

router = APIRouter()

# --- MOUNT ROUTERS ---

# 3. Mount Members (PROTECTED)
router.include_router(
    members_router, 
    tags=["Eurobot Members"], 
    dependencies=[Depends(verify_bot_token)]
)

# 4. Mount Channels Internal (PROTECTED)
# Result: /hoviat/v1/eurobot/channels/update_post (Requires Token)
router.include_router(
    channels_router, 
    prefix="/channels", 
    tags=["Eurobot Channels"],
    dependencies=[Depends(verify_bot_token)] 
)

# 5. Mount Channels Webhook (UNPROTECTED/PUBLIC)
# Result: /hoviat/v1/eurobot/set_group_message_id_test (No Token)
# We use prefix="" so it sits directly under /eurobot/ as requested
router.include_router(
    channels_webhook_router,
    prefix="", 
    tags=["Eurobot Webhooks"],
    # Explicitly NO dependencies list here
)