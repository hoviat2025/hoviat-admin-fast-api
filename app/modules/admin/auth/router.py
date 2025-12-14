from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm

# Note: We do NOT use StandardResponse for login.
# OAuth2 specs and Swagger UI require the 'access_token' field to be 
# at the root level of the JSON response, not inside "data".
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
    
    Returns the TokenResponse directly (unwrapped) so Swagger UI 
    and standard OAuth2 clients can parse the 'access_token' automatically.
    """
    # service.authenticate returns the TokenResponse Pydantic model
    result = await service.authenticate(
        username=form_data.username, 
        password=form_data.password
    )
    
    # Return directly (No StandardResponse wrapper)
    return result