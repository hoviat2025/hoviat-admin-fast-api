from fastapi import FastAPI
from app.core.config import settings
from app.core.exceptions import register_exception_handlers  # <--- NEW IMPORT

# --- IMPORTS ---
# 1. Admin Router
from app.modules.admin.router import router as admin_router
# 2. Eurobot Router
from app.modules.eurobot.router import router as eurobot_router
# 3. Shared Router
from app.shared.routers.user_lookup import router as shared_user_router

app = FastAPI(title="Unified API")

# --- REGISTER EXCEPTION HANDLERS ---
# This activates the global wrapper for errors (404, 409, 422, 500)
register_exception_handlers(app)

# --- APP MODE LOGIC ---
mode = settings.APP_MODE

print(f"🚀 Starting App in Mode: {mode}")

# --- MOUNT ROUTERS ---

# 1. Shared Router
app.include_router(
    shared_user_router, 
    prefix="/api/shared", 
    tags=["Shared Lookup"]
)

# 2. Admin Module
if mode == "admin" or mode == "all":
    app.include_router(admin_router, prefix="/api/admin")

# 3. Eurobot Module
if mode == "eurobot" or mode == "all":
    app.include_router(
        eurobot_router, 
        prefix="/api/eurobot", 
        tags=["Eurobot Module"]
    )

@app.get("/health")
def health_check():
    return {"status": "ok", "mode": mode}