from fastapi import APIRouter
from app.modules.hilfen.members.router import router as members_router

router = APIRouter()

# Register sub-routers under Hilfen
router.include_router(
    members_router,
    tags=["Hilfen Members"]
)