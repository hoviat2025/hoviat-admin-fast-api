from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import jwt, JWTError
from passlib.context import CryptContext
from app.core.config import settings

# Initialize the hashing context using the Argon2 algorithm.
# 'deprecated="auto"' ensures that legacy hashes are updated if the configuration changes.
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifies a plain-text password against its salted hash.
    """
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """
    Generates a secure hash from a plain-text password.
    """
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Generates a signed JWT (JSON Web Token) for user authentication.
    
    Args:
        data: The payload to be encoded in the token (e.g., user_id).
        expires_delta: Optional custom duration for token validity.
    
    Returns:
        A signed JWT string.
    """
    # Create a copy to avoid mutating the original dictionary
    to_encode = data.copy()
    
    # Calculate expiration time using UTC for cross-server compatibility
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        # Fallback to a default 15-minute window if no delta is provided
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    
    # Update the payload with the "exp" (expiration) claim
    to_encode.update({"exp": expire})
    
    # Sign the token using the application's secret key and defined algorithm
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    
    return encoded_jwt