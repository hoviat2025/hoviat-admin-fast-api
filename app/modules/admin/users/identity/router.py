from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.core.database import get_db
from app.modules.admin.users.repository import AdminUserRepository
from app.modules.admin.users.identity.service import IdentityService
from app.modules.admin.users.identity.schemas import UserIdentityResponse

router = APIRouter()

# Dependency Injection
def get_service(db: AsyncSession = Depends(get_db)) -> IdentityService:
    repo = AdminUserRepository(db)
    return IdentityService(repo)

@router.get("/", response_model=List[UserIdentityResponse])
async def get_users(
    limit: int = 20, 
    service: IdentityService = Depends(get_service)
):
    """
    Get a list of users.
    The Service returns SQLAlchemy Models.
    FastAPI (Pydantic) automatically converts them to UserIdentityResponse JSON.
    """
    return await service.list_users(limit=limit)