from fastapi import APIRouter
from app.modules.admin.users.router import router as users_router

router = APIRouter()

# Mount the Users entity
# URL becomes: /admin/users/...
router.include_router(users_router, prefix="/users", tags=["Admin Users"])