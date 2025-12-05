from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from app.core.config import settings

# This URL tells Swagger UI where to send the password when you click the Lock icon
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/admin/auth/login")

async def get_current_admin(token: str = Depends(oauth2_scheme)) -> int:
    """
    Validates the JWT token.
    Returns: The Admin ID (int) if valid.
    Raises: 401 Unauthorized if invalid.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # 1. Decode the Token
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        
        user_id: str = payload.get("sub")
        role: str = payload.get("role")
        
        # 2. Validate Payload
        if user_id is None:
            raise credentials_exception
            
        if role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, 
                detail="Not enough permissions"
            )
            
        return int(user_id)
        
    except JWTError:
        raise credentials_exception