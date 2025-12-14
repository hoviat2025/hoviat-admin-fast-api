from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm

from app.modules.admin.auth.schemas.login import TokenResponse
from app.modules.admin.auth.services.login import LoginService
from app.modules.admin.auth.dependencies import get_login_service

router = APIRouter()

@router.post("/login", response_model=TokenResponse)
async def login_admin(
    form_data: OAuth2PasswordRequestForm = Depends(),
    service: LoginService = Depends(get_login_service)
):
    """
    Admin Login Endpoint. 
    Accepts form-data (username/password) and returns a Bearer Token.
    """
    return await service.authenticate(
        username=form_data.username, 
        password=form_data.password
    )