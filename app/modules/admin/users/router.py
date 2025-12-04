from fastapi import APIRouter
from app.modules.admin.users.identity.router import router as identity_router
# Later you will add: from app.modules.admin.users.moderation.router import router as moderation_router

router = APIRouter()

# Mount the Identity feature
# URL becomes: /admin/users/identity
router.include_router(identity_router, prefix="/identity")

# Later: router.include_router(moderation_router, prefix="/moderation")