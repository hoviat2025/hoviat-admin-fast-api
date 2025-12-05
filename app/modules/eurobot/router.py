from fastapi import APIRouter, Depends
from app.modules.eurobot.dependencies import verify_bot_token

# We apply the "Bot Token" lock to this router.
# Any future endpoint you add here will automatically require the token.
router = APIRouter(dependencies=[Depends(verify_bot_token)])

@router.get("/ping")
async def ping_bot():
    """
    Placeholder endpoint to ensure the Eurobot module loads correctly.
    Verifies that the Bot Token is working.
    """
    return {"message": "Eurobot module is active and authenticated"}