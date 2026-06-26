from fastapi import APIRouter
from app.modules.hilfen.members.router import router as members_router
from app.modules.hilfen.channels.router import router as channels_router

router = APIRouter()

# Mount Protected Member Endpoints
router.include_router(
    members_router,
    tags=["Hilfen Members"]
)

# Mount Unprotected Webhook Endpoints (Telegram APIs)
router.include_router(
    channels_router,
    tags=["Hilfen Webhooks"]
)