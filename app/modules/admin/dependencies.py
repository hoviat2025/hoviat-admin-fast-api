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

# ---------------------------------------------------------
# 1. REPOSITORY INJECTION
# ---------------------------------------------------------

def get_admin_repository(db: AsyncSession = Depends(get_db)) -> AdminRepository:
    """
    Provides the AdminRepository to any Admin sub-module.
    """
    return AdminRepository(db)

# ---------------------------------------------------------
# 2. AUTHENTICATION (Login Check)
# ---------------------------------------------------------

async def get_current_admin(
    token: str = Depends(oauth2_scheme),
    repo: AdminRepository = Depends(get_admin_repository)
) -> Admin:
    """
    Validates JWT and checks DB for Admin existence/status.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
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
        
        admin = await repo.get_by_id(int(user_id))
        
        if admin is None:
            raise credentials_exception
            
        if not admin.is_active:
            raise HTTPException(status_code=400, detail="Admin account is inactive")
            
        return admin

    except (JWTError, ValueError):
        raise credentials_exception

# ---------------------------------------------------------
# 3. AUTHORIZATION (Permission Checks)
# ---------------------------------------------------------

async def require_read_users_permission(
    admin: Admin = Depends(get_current_admin)
) -> Admin:
    """
    Async Dependency.
    Ensures Admin has 'read_users' rights (via Superadmin or All Rights flag).
    """
    if admin.is_superadmin or admin.has_all_rights:
        return admin

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN, 
        detail="You do not have permission to view users."
    )