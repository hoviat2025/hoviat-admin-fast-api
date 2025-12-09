from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.core.config import settings
from app.core.exceptions import register_exception_handlers

# --- IMPORTS ---
from app.modules.admin.router import router as admin_router
from app.modules.eurobot.router import router as eurobot_router

# Import the Singleton Client
from app.shared.clients.telegram import telegram_client
# Assuming you have a storage client set up similarly (optional but recommended)
from app.shared.clients.storage import storage_client

# --- LIFESPAN MANAGER ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Startup: Open connections
    print("🚀 Starting up... Initializing Clients")
    await telegram_client.start()
    storage_client.start() 

    yield # Application runs here
    
    # 2. Shutdown: Close connections
    print("🛑 Shutting down... Closing Clients")
    await telegram_client.stop()
    storage_client.stop()

# --- APP SETUP ---
app = FastAPI(
    title="Unified API",
    lifespan=lifespan  # <--- Bind the manager here
)

# --- REGISTER EXCEPTION HANDLERS ---
register_exception_handlers(app)

# --- APP MODE LOGIC ---
mode = settings.APP_MODE

print(f"🚀 Starting App in Mode: {mode}")

# --- MOUNT ROUTERS ---
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