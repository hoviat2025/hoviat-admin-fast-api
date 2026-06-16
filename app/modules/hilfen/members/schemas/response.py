from pydantic import BaseModel
from app.models.user import User

class HilfenUserResponse(BaseModel):
    id: str
    user_id: str
    phonenumber: str
    idcart_photo: str
    all_projects: str
    all_projects_done: str
    limits_time: str
    name: str
    country: str
    status: str
    date_join: str
    command: str
    data: str

    class Config:
        from_attributes = True

    @classmethod
    def from_db_model(cls, user: User) -> "HilfenUserResponse":
        """
        Transforms the unified internal DB representation back to legacy formats 
        so Hilfen codebases can consume endpoints seamlessly.
        """
        first_name = user.first_name or ""
        last_name = user.last_name or ""
        full_name = f"{first_name} {last_name}".strip()

        return cls(
            id=str(user.hilfen_id or ""),
            user_id=str(user.user_id or ""),
            phonenumber=user.phone_number or "",
            idcart_photo=user.hilfen_id_card_photo or "",
            all_projects=str(user.hilfen_all_projects or 0),
            all_projects_done=str(user.hilfen_all_projects_done or 0),
            limits_time=str(user.hilfen_limits_time or 0),
            name=full_name,
            country=user.country or "",
            status=user.hilfen_status or "notconfirm",
            date_join=str(user.hilfen_date_join or ""),
            command=user.hilfen_command or "none",
            data=user.hilfen_data or "[]",
        )