from fastapi import APIRouter, Depends
from app.modules.admin.dependencies import get_current_admin

# Import Sub-Routers
from app.modules.admin.users_management.router import router as users_management_router
from app.modules.admin.auth.router import router as auth_router

# The Main Admin Router
router = APIRouter()

# 1. PUBLIC ROUTES (Login)
router.include_router(auth_router, prefix="/auth", tags=["Admin Auth"])

# 2. PROTECTED ROUTES
# Requires Login (get_current_admin)
router.include_router(
    users_management_router, 
    prefix="/users-management", 
    tags=["Admin Users Management"],
    dependencies=[Depends(get_current_admin)] 
)