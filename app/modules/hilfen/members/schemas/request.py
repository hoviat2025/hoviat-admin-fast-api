from pydantic import BaseModel
from typing import Optional

from app.shared.user_update_policy import PROTECTED_FROM_NULL_FIELDS

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
        Translates legacy Hilfen fields for partial updates, applying the
        nullification policy (see app/shared/user_update_policy.py).

        Rule of thumb:
          - PROTECTED fields (identity/contact, incl. hilfen_id/date_join):
            an empty value ("") is treated as "I did not provide this" and the
            field is skipped entirely. An existing value can never be wiped
            with an empty string or null.
          - NON-protected fields: passed through as-is - an explicit "" or
            null is written verbatim (the client owns those fields). The only
            exception: integer columns cannot store "", so an empty value
            becomes NULL there instead of the insert-time default of 0.
        """
        # "name" is a legacy composite that maps to first_name + last_name.
        update_data = {}

        def is_empty(value) -> bool:
            return value is None or (isinstance(value, str) and not value.strip())

        def is_numeric_db_field(db_field: str) -> bool:
            return db_field in {
                "hilfen_all_projects",
                "hilfen_all_projects_done",
                "hilfen_limits_time",
            }

        if "name" in self.model_fields_set:
            name_str = (self.name or "").strip()
            if " " in name_str:
                first_name, last_name = name_str.split(" ", 1)
            else:
                first_name, last_name = name_str, ""
            for db_field, value in (("first_name", first_name), ("last_name", last_name)):
                # Protected: empty means "not provided", never a wipe.
                if is_empty(value):
                    continue
                update_data[db_field] = value

        legacy_to_db_fields = {
            "id": ("hilfen_id",),
            "phonenumber": ("phone_number",),
            "idcart_photo": ("hilfen_id_card_photo",),
            "all_projects": ("hilfen_all_projects",),
            "all_projects_done": ("hilfen_all_projects_done",),
            "limits_time": ("hilfen_limits_time",),
            "country": ("country",),
            "status": ("hilfen_status",),
            "date_join": ("hilfen_date_join",),
            "command": ("hilfen_command",),
            "data": ("hilfen_data",),
        }

        for legacy_field, db_fields in legacy_to_db_fields.items():
            if legacy_field not in self.model_fields_set:
                continue

            raw = getattr(self, legacy_field)

            for db_field in db_fields:
                # Protected + empty: skip, keep the stored value untouched.
                if db_field in PROTECTED_FROM_NULL_FIELDS:
                    if is_empty(raw):
                        continue
                    # Protected numeric identifiers: only real digits may be
                    # written; garbage must never erase the stored value, so
                    # it is skipped like an empty value.
                    if not raw.isdigit():
                        continue
                    update_data[db_field] = int(raw)
                    continue

                # Non-protected, owned by the client:
                #   - integer columns: digits -> int, empty/garbage -> NULL
                #   - string columns: written verbatim ("" stays "")
                if is_numeric_db_field(db_field):
                    update_data[db_field] = int(raw) if raw.isdigit() else None
                else:
                    update_data[db_field] = raw

        return update_data
