from fastapi import APIRouter

from app.modules.sns.auth.router import router as auth_router
from app.modules.sns.account.router import router as account_router
from app.modules.sns.profiles.router import router as profiles_router
from app.modules.sns.bookmarks.router import router as bookmarks_router
from app.modules.sns.owned_services.router import router as owned_services_router
from app.modules.sns.service_bookmarks.router import router as service_bookmarks_router

router = APIRouter()

# 1. Auth (e.g., /sns/auth/telegram)
router.include_router(auth_router, prefix="/auth", tags=["SNS Auth"])

# 2. Account (e.g., /sns/account/me)
router.include_router(account_router, prefix="/account", tags=["SNS Account"])

# 3. Profiles (e.g., /sns/profiles/search)
router.include_router(profiles_router, prefix="/profiles", tags=["SNS Profiles"])

# 4. Bookmarks (e.g., /sns/bookmarks)
router.include_router(bookmarks_router, prefix="/bookmarks", tags=["SNS Bookmarks"])

# Business ownership is separate from the personal profile and staff admin API.
router.include_router(owned_services_router, prefix="/me/services", tags=["SNS My Services"])

router.include_router(
    service_bookmarks_router,
    prefix="/me/service-bookmarks",
    tags=["SNS Business Bookmarks"],
)
