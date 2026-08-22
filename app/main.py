import logging
import sys
import asyncio  # <-- Added to manage background tasks
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends  # <-- Added Depends for DB injection
from sqlalchemy.ext.asyncio import AsyncSession  # <-- Added for database type hinting
from app.core.config import settings
from app.core.cron_auth import require_cron_secret
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
from app.modules.sns.router import router as sns_router

from app.shared.clients.storage import storage_client
# Import queue startup recovery and the two worker lane runners
from app.shared.queue_worker import (
    recover_orphaned_jobs,
    run_background_queue_worker,
    run_vip_queue_worker,
)
from app.shared.cron_sync_service import CronSyncService  # <-- Imported universal cron service
from app.core.database import get_db  # <-- Imported database dependency

# --- LIFESPAN MANAGER ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Startup
    logger.info("🚀 Starting up...")
    # Recovery must succeed before either worker can consume queue rows.
    logger.info("Recovering abandoned queue jobs...")
    await recover_orphaned_jobs()

    storage_client.start()

    # Launch both queue workers only after recovery has completed.
    logger.info("⚙️ Initializing concurrent queue worker lanes...")
    background_worker_task = asyncio.create_task(run_background_queue_worker())
    vip_worker_task = asyncio.create_task(run_vip_queue_worker())

    yield # Application runs here
    
    # 2. Shutdown
    logger.info("🛑 Shutting down...")
    
    # Cancel both background worker loops and wait for them to cleanly stop
    logger.info("🛑 Cancelling queue worker loops...")
    background_worker_task.cancel()
    vip_worker_task.cancel()
    
    # Cleanly await termination results of both tasks
    results = await asyncio.gather(
        background_worker_task,
        vip_worker_task,
        return_exceptions=True
    )
    
    for i, res in enumerate(results):
        lane_name = "Background Lane" if i == 0 else "VIP Lane"
        if isinstance(res, asyncio.CancelledError):
            logger.info(f"✅ {lane_name} stopped successfully.")
        elif isinstance(res, Exception):
            logger.error(f"❌ Error while shutting down {lane_name}: {res}")

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

if mode == "sns" or mode == "all":
    # Mount SNS user panel
    app.include_router(
        sns_router,
        prefix="/api/sns",
        tags=["SNS Module"]
    )

@app.get("/health")
async def health_check():  # Added 'async'
    return {"status": "ok", "mode": mode}

# --- UNIVERSAL CRON ENDPOINT ---
@app.post("/webhook/hoviat/v1/cron-sync", dependencies=[Depends(require_cron_secret)])
async def trigger_cron_sync(db: AsyncSession = Depends(get_db)):
    """
    Exposes a secure POST webhook endpoint to trigger the universal cron sync.
    Can be pinged periodically by external schedulers (e.g. Linux Crontab, cron-job.org).
    """
    logger.info("🔄 Triggering universal database cron synchronization...")
    service = CronSyncService(db)
    result = await service.execute(batch_size=20)
    return result
