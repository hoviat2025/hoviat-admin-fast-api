from pydantic import BaseModel, ConfigDict, field_serializer, BeforeValidator
from typing import Optional, Annotated, Any, Dict
from datetime import datetime

# --- 1. Define a Helper Helper Function ---
def force_to_string(v: Any) -> Optional[str]:
    """
    Takes any value (like an int from DB) and turns it into a string
    BEFORE Pydantic tries to validate it.
    """
    if v is None:
        return None
    return str(v)

# --- 2. Create a Custom Type ---
# This says: "This field is a String, but run 'force_to_string' on the input first."
StringifiedInt = Annotated[str, BeforeValidator(force_to_string)]


class BotUserResponse(BaseModel):
    
    # --- 3. Apply the Custom Type to the ID/Number fields ---
    user_id: StringifiedInt
    ban_time: Optional[StringifiedInt] = None
    join_date: Optional[StringifiedInt] = None
    
    # These fields were already strings or didn't have issues, 
    # but using StringifiedInt is safer if your DB might return ints here too.
    telegram_message_id: Optional[StringifiedInt] = None
    group_message_id: Optional[StringifiedInt] = None
    public_message_id: Optional[StringifiedInt] = None
    public_group_message_id: Optional[StringifiedInt] = None

    # --- Standard Fields ---
    counter: Optional[int] = None
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    nickname: Optional[str] = None
    phone_number: Optional[str] = None
    whatsapp_number: Optional[str] = None
    country: Optional[str] = None
    password: Optional[str] = None
    mode: Optional[str] = None
    accounting_code: Optional[str] = None
    
    is_ban: Optional[bool] = None
    is_registered: Optional[bool] = None
    chat_not_found: bool = False

    score: Optional[int] = None
    profile_path: Optional[str] = None

    updated_at: datetime
    channel_updated_at: Optional[datetime] = None
    field_updated_at: Dict[str, Optional[datetime]]

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True
    )

    # --- 4. Keep the Date Serializer (For Formatting) ---
    @field_serializer('updated_at', 'channel_updated_at')
    def serialize_datetime(self, value: datetime, _info):
        """Formats datetime to ISO with milliseconds and Z suffix."""
        if value is None:
            return None
        # Format: 2025-12-07T14:25:01.112Z
        return value.isoformat(timespec='milliseconds').replace("+00:00", "Z")

    @field_serializer('field_updated_at')
    def serialize_field_datetimes(self, values, _info):
        return {
            field: (
                value.isoformat(timespec='milliseconds').replace("+00:00", "Z")
                if value is not None
                else None
            )
            for field, value in values.items()
        }
