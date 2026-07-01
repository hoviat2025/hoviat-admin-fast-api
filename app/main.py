import logging
import sys
import asyncio  # <-- Added to manage background tasks
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends  # <-- Added Depends for DB injection
from sqlalchemy.ext.asyncio import AsyncSession  # <-- Added for database type hinting
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.middleware import register_middleware

# 🔴 NEW LOGGING SETUP: This forces logs to print beautifully in FastAPI
logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    force=True # Forces Uvicorn to use our format
)
logger = logging.getLogger(__name__)

# --- IMPORTS ---
from app.modules.admin.router import router as admin_router
from app.modules.eurobot.router import router as eurobot_router
from app.modules.hilfen.router import router as hilfen_router

from app.shared.clients.storage import storage_client
from app.shared.queue_worker import run_queue_worker  # <-- Imported queue worker loop
from app.shared.cron_sync_service import CronSyncService  # <-- Imported universal cron service
from app.core.database import get_db  # <-- Imported database dependency

# --- LIFESPAN MANAGER ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Startup
    logger.info("🚀 Starting up...")
    storage_client.start() 

    # Launch the queue worker task in the background (Non-blocking)
    logger.info("⚙️ Initializing background queue worker...")
    worker_task = asyncio.create_task(run_queue_worker())

    yield # Application runs here
    
    # 2. Shutdown
    logger.info("🛑 Shutting down...")
    
    # Cancel the background worker loop and wait for it to cleanly stop
    logger.info("🛑 Cancelling queue worker loop...")
    worker_task.cancel()
    try:
        await worker_task
    except asyncio.CancelledError:
        logger.info("✅ Queue worker loop stopped successfully.")
    except Exception as e:
        logger.error(f"❌ Error while shutting down queue worker: {e}")

    storage_client.stop()

# --- APP SETUP ---
app = FastAPI(
    title="Unified API",
    lifespan=lifespan
)

register_middleware(app)
register_exception_handlers(app)

mode = settings.APP_MODE
logger.info(f"🚀 Starting App in Mode: {mode}")

if mode == "admin" or mode == "all":
    app.include_router(admin_router, prefix="/api/admin")

if mode == "eurobot" or mode == "all":
    # Mount Eurobot
    app.include_router(
        eurobot_router, 
        prefix="/webhook/hoviat/v1/eurobot", 
        tags=["Eurobot Module"]
    )
    # Mount Hilfen (unprotected endpoints for initial verification)
    app.include_router(
        hilfen_router,
        prefix="/webhook/hoviat/v1/hilfen",
        tags=["Hilfen Module"]
    )

@app.get("/health")
async def health_check():  # Added 'async'
    return {"status": "ok", "mode": mode}

# --- UNIVERSAL CRON ENDPOINT ---
@app.post("/webhook/hoviat/v1/cron-sync")
async def trigger_cron_sync(db: AsyncSession = Depends(get_db)):
    """
    Exposes a secure POST webhook endpoint to trigger the universal cron sync.
    Can be pinged periodically by external schedulers (e.g. Linux Crontab, cron-job.org).
    """
    logger.info("🔄 Triggering universal database cron synchronization...")
    service = CronSyncService(db)
    result = await service.execute(batch_size=20)
    return result