from fastapi import APIRouter, Depends
# 1. Re-import the dependency
from app.modules.eurobot.dependencies import verify_bot_token

# 2. Import your sub-routers
from app.modules.eurobot.members.router import router as members_router
from app.modules.eurobot.channels.router import router as channels_router 

router = APIRouter()

# --- MOUNT ROUTERS ---

# 3. Mount Members (PROTECTED)
router.include_router(
    members_router, 
    tags=["Eurobot Members"], 
    dependencies=[Depends(verify_bot_token)] # <--- Kept this
)

# 4. Mount Channels (PROTECTED)
# We apply the same protection here so only authorized requests 
# (from Telegram or your own Admin panel sending the token) can trigger updates.
router.include_router(
    channels_router, 
    prefix="/channels", 
    tags=["Eurobot Channels"],
    dependencies=[Depends(verify_bot_token)] # <--- Added this
)