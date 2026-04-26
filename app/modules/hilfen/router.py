from fastapi import APIRouter, Request

from app.modules.hilfen.core.dispatcher import process_telegram_update

router = APIRouter()


@router.post("/webhook")
async def telegram_webhook(request: Request):
    """
    Telegram webhook endpoint.

    This endpoint intentionally does NOT initialize a database session.
    The dispatcher is responsible for creating a DB session only if
    stateful handlers require it.
    """
    update_data = await request.json()

    await process_telegram_update(update_data)

    return {"status": "ok"}
