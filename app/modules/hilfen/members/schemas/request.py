from pydantic import BaseModel
from typing import Optional

class HilfenInsertMemberRequest(BaseModel):
    id: str
    user_id: str
    phonenumber: Optional[str] = ""
    idcart_photo: Optional[str] = ""
    all_projects: Optional[str] = "0"
    all_projects_done: Optional[str] = "0"
    limits_time: Optional[str] = "0"
    name: Optional[str] = ""
    country: Optional[str] = ""
    status: Optional[str] = "notconfirm"
    date_join: Optional[str] = ""
    command: Optional[str] = "none"
    data: Optional[str] = "[]"

    def to_db_dict(self) -> dict:
        """
        Translates the legacy Hilfen properties to map cleanly with the database schema context.
        Converts empty values and handles name token-splitting for unified fields.
        """
        name_str = (self.name or "").strip()
        if " " in name_str:
            first_name, last_name = name_str.split(" ", 1)
        else:
            first_name = name_str
            last_name = ""

        user_id_int = int(self.user_id) if self.user_id.isdigit() else None

        return {
            "user_id": user_id_int,
            
            "phone_number": self.phonenumber if self.phonenumber else None,
            "country": self.country if self.country else None,
            "first_name": first_name if first_name else None,
            "last_name": last_name if last_name else None,
            
            # Hilfen-specific properties
            "hilfen_id": int(self.id) if self.id.isdigit() else None,
            "hilfen_status": self.status,
            "hilfen_date_join": int(self.date_join) if self.date_join.isdigit() else None,
            "hilfen_command": self.command,
            "hilfen_data": self.data,
            "hilfen_id_card_photo": self.idcart_photo,
            "hilfen_all_projects": int(self.all_projects) if self.all_projects.isdigit() else 0,
            "hilfen_all_projects_done": int(self.all_projects_done) if self.all_projects_done.isdigit() else 0,
            "hilfen_limits_time": int(self.limits_time) if self.limits_time.isdigit() else 0,
        }

    def to_update_dict(self) -> dict:
        """
        Translates legacy Hilfen fields for partial updates.
        Reuses to_db_dict() translation logic but excludes unset fields and primary key.
        """
        full = self.to_db_dict()
        legacy_to_db_fields = {
            "id": ("hilfen_id",),
            "phonenumber": ("phone_number",),
            "idcart_photo": ("hilfen_id_card_photo",),
            "all_projects": ("hilfen_all_projects",),
            "all_projects_done": ("hilfen_all_projects_done",),
            "limits_time": ("hilfen_limits_time",),
            "name": ("first_name", "last_name"),
            "country": ("country",),
            "status": ("hilfen_status",),
            "date_join": ("hilfen_date_join",),
            "command": ("hilfen_command",),
            "data": ("hilfen_data",),
        }

        update_data = {}
        for legacy_field in self.model_fields_set - {"user_id"}:
            for db_field in legacy_to_db_fields.get(legacy_field, ()):
                update_data[db_field] = full[db_field]

        return update_data
