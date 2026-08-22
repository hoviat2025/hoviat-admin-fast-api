from typing import Optional

from pydantic import BaseModel


class TelegramLoginRequest(BaseModel):
    """
    Payload sent by the Telegram Login Widget onAuth callback.
    All fields (except hash) are used verbatim to recompute the HMAC.
    """
    id: int
    first_name: str
    last_name: Optional[str] = None
    username: Optional[str] = None
    photo_url: Optional[str] = None
    auth_date: int
    hash: str


class TelegramLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    first_name: str
    username: Optional[str] = None
