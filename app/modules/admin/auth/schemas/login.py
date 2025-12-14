from pydantic import BaseModel, Field

class TokenResponse(BaseModel):
    """
    Response model specifically for the Login endpoint.
    """
    access_token: str = Field(..., description="JWT Access Token")
    token_type: str = Field(..., description="Type of token (Bearer)")
    expires_in: int = Field(..., description="Expiration in seconds")
    
    # Returning user info helps the frontend set up the UI immediately
    username: str
    is_superadmin: bool