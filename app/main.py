import logging
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI
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

# --- LIFESPAN MANAGER ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Startup
    logger.info("🚀 Starting up...")
    storage_client.start() 

    yield # Application runs here
    
    # 2. Shutdown
    logger.info("🛑 Shutting down...")
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