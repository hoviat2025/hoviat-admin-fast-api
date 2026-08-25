from pydantic import BaseModel


class BotLoginRequest(BaseModel):
    """
    Payload sent by the SNS bot when a user asks to log in to the website.
    Identity fields are optional; whatever is provided is upserted immediately
    so the profile row exists before the token is even exchanged.
    """
    user_id: int
    first_name: str | None = None
    last_name: str | None = None
    username: str | None = None


class BotLoginResponse(BaseModel):
    login_token: str
    expires_in: int


class TokenExchangeRequest(BaseModel):
    """The short-lived token the user pasted into the website."""
    token: str
