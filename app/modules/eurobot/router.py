from fastapi import APIRouter, Depends
from app.modules.eurobot.dependencies import verify_bot_token

# Import the Group Router
from app.modules.eurobot.members.router import router as members_router

router = APIRouter()

# Mount the Members group
# We apply the dependency HERE so all member routes are protected
router.include_router(
    members_router, 
    tags=["Eurobot Members"], 
    dependencies=[Depends(verify_bot_token)]
)