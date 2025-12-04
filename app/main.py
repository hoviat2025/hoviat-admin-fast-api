from fastapi import FastAPI
from app.core.config import settings

# Import the top-level module routers
from app.modules.admin.router import router as admin_router
# from app.modules.bot.router import router as bot_router  <-- Commented until you build it

app = FastAPI(title="Unified API")

# --- APP MODE LOGIC ---
# We check the .env variable to decide what to load
mode = settings.APP_MODE

print(f"🚀 Starting App in Mode: {mode}")

if mode == "admin" or mode == "all":
    app.include_router(admin_router, prefix="/api/admin")

# if mode == "bot" or mode == "all":
#     app.include_router(bot_router, prefix="/api/bot")

@app.get("/health")
def health_check():
    return {"status": "ok", "mode": mode}