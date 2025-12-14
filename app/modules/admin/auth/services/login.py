from datetime import timedelta
from fastapi import HTTPException, status

from app.core.security import verify_password, create_access_token
from app.core.config import settings
from app.modules.admin.repositories.admin import AdminRepository
from app.modules.admin.auth.schemas.login import TokenResponse

class LoginService:
    """
    Business logic for Admin Login.
    """
    def __init__(self, admin_repo: AdminRepository):
        self.admin_repo = admin_repo

    async def authenticate(self, username: str, password: str) -> TokenResponse:
        """
        Verifies credentials, checks active status, and issues a 7-day JWT.
        """
        # 1. Fetch User
        admin = await self.admin_repo.get_by_username(username)

        # 2. Generic Error (Security Best Practice)
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

        # 3. Verify
        if not admin:
            raise credentials_exception

        if not verify_password(password, admin.password_hash):
            raise credentials_exception

        if not admin.is_active:
             raise HTTPException(status_code=400, detail="Admin account is inactive")

        # 4. Create Token
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        
        token = create_access_token(
            data={
                "sub": str(admin.id), 
                "role": "admin",
                "super": admin.is_superadmin
            },
            expires_delta=access_token_expires
        )
        
        return TokenResponse(
            access_token=token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            username=admin.username,
            is_superadmin=admin.is_superadmin
        )