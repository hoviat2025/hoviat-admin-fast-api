from pydantic import BaseModel, Field

class TokenResponse(BaseModel):
    access_token: str = Field(..., description="The JWT access token")
    token_type: str = Field(..., description="The token type, usually 'bearer'")
    
    # Optional: You can include expiry or user info here if the frontend needs it
    expires_in: int = Field(..., description="Seconds until expiration")