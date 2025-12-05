from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import timedelta

from app.models.admin import Admin
from app.core.security import verify_password, create_access_token
from app.core.config import settings
from app.modules.admin.auth.schemas import TokenResponse

class AdminAuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def authenticate_admin(self, username: str, password: str) -> TokenResponse:
        # 1. Fetch Admin by Username
        query = select(Admin).where(Admin.username == username)
        result = await self.db.execute(query)
        admin = result.scalars().first()

        # 2. Security Check: Invalid User
        # We use the same generic error message to prevent "User Enumeration" attacks
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

        if not admin:
            raise credentials_exception

        # 3. Security Check: Invalid Password (Argon2 Verify)
        if not verify_password(password, admin.password_hash):
            raise credentials_exception
            
        # 4. Security Check: Is Active?
        if not admin.is_active:
             raise HTTPException(status_code=400, detail="Admin account is inactive")

        # 5. Generate JWT
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        
        # We embed the Admin ID ('sub') and Role ('role') into the token
        token = create_access_token(
            data={"sub": str(admin.id), "role": "admin", "username": admin.username},
            expires_delta=access_token_expires
        )
        
        return TokenResponse(
            access_token=token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )