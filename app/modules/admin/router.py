from fastapi import APIRouter, Depends
from app.modules.admin.dependencies import get_current_admin

# Import Sub-Routers
from app.modules.admin.users.router import router as users_router
from app.modules.admin.auth.router import router as auth_router

# The Main Admin Router
router = APIRouter()

# 1. PUBLIC ROUTES (Login) - No Dependency
router.include_router(auth_router, prefix="/auth", tags=["Admin Auth"])

# 2. PROTECTED ROUTES - Require 'get_current_admin'
# Any router added here will require a valid JWT
router.include_router(
    users_router, 
    prefix="/users", 
    tags=["Admin Users"],
    dependencies=[Depends(get_current_admin)] 
)