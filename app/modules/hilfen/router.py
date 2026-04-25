from fastapi import APIRouter

# Initialize the router for the Hilfen module
router = APIRouter()

# --- MOUNT ROUTERS / ENDPOINTS ---

@router.get("/test")
async def hilfen_test_endpoint():
    """
    Basic test endpoint to verify the Hilfen module is connected properly.
    """
    return {"module": "hilfen", "status": "success", "message": "Hilfen handler is running!"}

# Later, you can import and mount sub-routers here just like in eurobot:
# from app.modules.hilfen.some_feature.router import router as some_feature_router
# router.include_router(some_feature_router, prefix="/feature")
