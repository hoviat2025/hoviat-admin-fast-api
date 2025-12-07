from fastapi import FastAPI
from app.core.config import settings
from app.core.exceptions import register_exception_handlers

# --- IMPORTS ---
# 1. Admin Router
from app.modules.admin.router import router as admin_router
# 2. Eurobot Router
from app.modules.eurobot.router import router as eurobot_router

# REMOVED: Shared Router import (We rely on Shared Repositories now)

app = FastAPI(title="Unified API")

# --- REGISTER EXCEPTION HANDLERS ---
register_exception_handlers(app)

# --- APP MODE LOGIC ---
mode = settings.APP_MODE

print(f"🚀 Starting App in Mode: {mode}")

# --- MOUNT ROUTERS ---

# 1. Admin Module
if mode == "admin" or mode == "all":
    app.include_router(admin_router, prefix="/api/admin")

# 2. Eurobot Module
if mode == "eurobot" or mode == "all":
    app.include_router(
        eurobot_router, 
        prefix="/webhook/hoviat/v1/eurobot", 
        tags=["Eurobot Module"]
    )

# REMOVED: Shared Router Mount

@app.get("/health")
def health_check():
    return {"status": "ok", "mode": mode}