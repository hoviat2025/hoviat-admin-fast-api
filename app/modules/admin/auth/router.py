from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.admin.auth.service import AdminAuthService
from app.modules.admin.auth.schemas import TokenResponse

router = APIRouter()

# Dependency Injection for the Service
def get_auth_service(db: AsyncSession = Depends(get_db)) -> AdminAuthService:
    return AdminAuthService(db)

@router.post("/login", response_model=TokenResponse)
async def login_admin(
    form_data: OAuth2PasswordRequestForm = Depends(),
    service: AdminAuthService = Depends(get_auth_service)
):
    """
    OAuth2 compatible token login, get an access token for future requests.
    """
    # Note: form_data.username and form_data.password come from the request body
    return await service.authenticate_admin(
        username=form_data.username, 
        password=form_data.password
    )