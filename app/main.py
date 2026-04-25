from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.middleware import register_middleware

# --- MODULE ROUTERS ---
from app.modules.admin.router import router as admin_router
from app.modules.eurobot.router import router as eurobot_router
from app.modules.hilfen.router import router as hilfen_router

# --- SHARED CLIENTS ---
from app.shared.clients.storage import storage_client

# --- LIFESPAN MANAGER ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize shared connections and background tasks on application startup
    print("🚀 Starting up...")
    storage_client.start() 

    yield # Application handles requests during this phase
    
    # Gracefully close connections and clean up resources on application shutdown
    print("🛑 Shutting down...")
    storage_client.stop()

# --- APPLICATION FACTORY ---
app = FastAPI(
    title="Unified API",
    lifespan=lifespan
)

# Register global configurations
register_middleware(app)
register_exception_handlers(app)

# --- ROUTER MOUNTING ---
# The application runs in different modes (admin, eurobot, hilfen, or all) based on environment configuration.
# Only the routers required for the active mode are mounted to save resources and restrict endpoints.
mode = settings.APP_MODE
print(f"🚀 Starting App in Mode: {mode}")

if mode in ("admin", "all"):
    app.include_router(
        admin_router, 
        prefix="/api/admin",
        tags=["Admin Module"]
    )

if mode in ("eurobot", "all"):
    app.include_router(
        eurobot_router, 
        prefix="/webhook/hoviat/v1/eurobot", 
        tags=["Eurobot Module"]
    )

if mode in ("hilfen", "all"):
    app.include_router(
        hilfen_router, 
        prefix="/webhook/hoviat/v1/hilfen", 
        tags=["Hilfen Module"]
    )

# --- GLOBAL ENDPOINTS ---
@app.get("/health", tags=["System"])
async def health_check():
    """Provides a basic health check and exposes the current running mode."""
    return {"status": "ok", "mode": mode}
