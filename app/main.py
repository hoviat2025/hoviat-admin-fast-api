from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.middleware import register_middleware

# --- IMPORTS ---
from app.modules.admin.router import router as admin_router
from app.modules.eurobot.router import router as eurobot_router

from app.shared.clients.storage import storage_client

# --- LIFESPAN MANAGER ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Startup
    print("🚀 Starting up...")
    storage_client.start() 

    yield # Application runs here
    
    # 2. Shutdown
    print("🛑 Shutting down...")
    storage_client.stop()

# --- APP SETUP ---
app = FastAPI(
    title="Unified API",
    lifespan=lifespan
)

register_middleware(app)
register_exception_handlers(app)

mode = settings.APP_MODE
print(f"🚀 Starting App in Mode: {mode}")

if mode == "admin" or mode == "all":
    app.include_router(admin_router, prefix="/api/admin")

if mode == "eurobot" or mode == "all":
    app.include_router(
        eurobot_router, 
        prefix="/webhook/hoviat/v1/eurobot", 
        tags=["Eurobot Module"]
    )

@app.get("/health")
def health_check():
    return {"status": "ok", "mode": mode}