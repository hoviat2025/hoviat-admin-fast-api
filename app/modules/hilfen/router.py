from fastapi import APIRouter, Depends

from app.modules.hilfen.dependencies import verify_hilfen_token
from app.modules.hilfen.members.router import router as members_router
from app.modules.hilfen.channels.router import router as channels_router

router = APIRouter()

# Mount Protected Member Endpoints
router.include_router(
    members_router,
    tags=["Hilfen Members"],
    dependencies=[Depends(verify_hilfen_token)],
)

# Mount webhook endpoints (sender authentication is on the child router).
router.include_router(
    channels_router,
    tags=["Hilfen Webhooks"]
)
