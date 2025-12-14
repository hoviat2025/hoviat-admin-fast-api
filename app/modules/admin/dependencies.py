from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models.admin import Admin
from app.modules.admin.repositories.admin import AdminRepository

# Swagger UI configuration
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/admin/auth/login")

def get_admin_repository(db: AsyncSession = Depends(get_db)) -> AdminRepository:
    """
    Provides the AdminRepository to any Admin sub-module.
    """
    return AdminRepository(db)

async def get_current_admin(
    token: str = Depends(oauth2_scheme),
    repo: AdminRepository = Depends(get_admin_repository)
) -> Admin:
    """
    Validates the JWT token AND checks the Database for the Admin's existence and status.
    
    Returns:
        The Admin ORM object if valid and active.
        
    Raises:
        401: Invalid token, or Admin deleted.
        400: Admin is inactive (soft deleted).
        403: Not an admin role.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        # 1. Decode Token
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        role: str = payload.get("role")

        if user_id is None:
            raise credentials_exception
        
        if role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, 
                detail="Not enough permissions"
            )
        
        # 2. Check Database (Strict Revocation Check)
        admin = await repo.get_by_id(int(user_id))
        
        if admin is None:
            raise credentials_exception
            
        # 3. Check Active Status
        if not admin.is_active:
            raise HTTPException(status_code=400, detail="Admin account is inactive")
            
        return admin

    except (JWTError, ValueError):
        raise credentials_exception