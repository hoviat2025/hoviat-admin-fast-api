from typing import Optional

from pydantic import BaseModel


class TelegramLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    first_name: str
    username: Optional[str] = None
