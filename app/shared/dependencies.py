from fastapi import Security, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError

from app.core.config import settings

# We use HTTPBearer because it covers both OAuth2 (Admin) and Static Token (Bot)
# They both look like: "Authorization: Bearer <TOKEN>"
security = HTTPBearer()

def verify_shared_auth(credentials: HTTPAuthorizationCredentials = Security(security)):
    token = credentials.credentials

    # --- ATTEMPT 1: IS IT THE EUROBOT? ---
    # Logic: String match against env var
    if token == settings.BOT_API_TOKEN:
        return {"type": "bot", "id": "eurobot"}

    # --- ATTEMPT 2: IS IT AN ADMIN? ---
    # Logic: JWT Decode
    try:
        # We reuse the exact same settings used in the Admin module
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = payload.get("sub")
        role = payload.get("role")

        if user_id and role == "admin":
            return {"type": "admin", "id": user_id}
            
    except JWTError:
        # It wasn't a valid JWT either.
        pass

    # --- FAILURE: NEITHER KEY WORKED ---
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Access denied. Requires valid Admin JWT or Eurobot Token."
    )