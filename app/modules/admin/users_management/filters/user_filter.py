from typing import Optional
from datetime import datetime
from pydantic import Field, ConfigDict, field_validator
from fastapi_filter.contrib.sqlalchemy import Filter
from app.models.user import User

class UserFilter(Filter):
    """
    Comprehensive Filter for Users.
    
    Supports:
    1. Exact Match: ?field=value
    2. Partial Match: ?field_contains=value (Case-insensitive)
    3. Null Check: ?no_field=true
    4. Ranges: ?min_score=10, ?joined_after_unix=...
    """
    model_config = ConfigDict(
        extra='ignore',       # Allow pagination params (page, size) to pass through
        populate_by_name=True # Allow using both variable names and aliases
    )

    # ==========================================
    # 1. TEXT SEARCH (Exact & Partial)
    # ==========================================
    
    # --- Exact Matches ---
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    nickname: Optional[str] = None
    country: Optional[str] = None
    phone_number: Optional[str] = None
    whatsapp_number: Optional[str] = None
    profile_path: Optional[str] = None
    password: Optional[str] = None
    hilfen_data: Optional[str] = None
    hilfen_id_card_photo: Optional[str] = None

    # --- Partial Matches (Contains) ---
    username__ilike: Optional[str] = Field(default=None, alias="username_contains")
    first_name__ilike: Optional[str] = Field(default=None, alias="first_name_contains")
    last_name__ilike: Optional[str] = Field(default=None, alias="last_name_contains")
    nickname__ilike: Optional[str] = Field(default=None, alias="nickname_contains")
    country__ilike: Optional[str] = Field(default=None, alias="country_contains")
    phone_number__ilike: Optional[str] = Field(default=None, alias="phone_number_contains")
    whatsapp_number__ilike: Optional[str] = Field(default=None, alias="whatsapp_number_contains")
    profile_path__ilike: Optional[str] = Field(default=None, alias="profile_path_contains")
    accounting_code__ilike: Optional[str] = Field(default=None, alias="accounting_code_contains")
    password__ilike: Optional[str] = Field(default=None, alias="password_contains")
    mode__ilike: Optional[str] = Field(default=None, alias="mode_contains")
    hilfen_data__ilike: Optional[str] = Field(default=None, alias="hilfen_data_contains")
    hilfen_id_card_photo__ilike: Optional[str] = Field(default=None, alias="hilfen_id_card_photo_contains")

    # ==========================================
    # 2. EXACT MATCHES (IDs, Codes, Enums)
    # ==========================================

    counter: Optional[int] = None
    user_id: Optional[int] = None
    accounting_code: Optional[str] = None
    mode: Optional[str] = None
    score: Optional[int] = None
    ban_time: Optional[int] = None
    join_date: Optional[int] = None

    # Message IDs
    telegram_message_id: Optional[str] = None
    group_message_id: Optional[str] = None
    public_message_id: Optional[str] = None
    public_group_message_id: Optional[str] = None

    # Hilfen-specific fields
    hilfen_id: Optional[int] = None
    hilfen_status: Optional[str] = None
    hilfen_date_join: Optional[int] = None
    hilfen_command: Optional[str] = None
    hilfen_all_projects: Optional[int] = None
    hilfen_all_projects_done: Optional[int] = None
    hilfen_limits_time: Optional[int] = None
    hilfen_message_id: Optional[int] = None
    hilfen_group_message_id: Optional[int] = None

    hilfen_status__ilike: Optional[str] = Field(default=None, alias="hilfen_status_contains")
    hilfen_command__ilike: Optional[str] = Field(default=None, alias="hilfen_command_contains")

    # Bot membership
    is_in_eurobot: Optional[bool] = None
    is_in_hilfen_bot: Optional[bool] = None

    # ==========================================
    # 3. BOOLEANS
    # ==========================================

    is_ban: Optional[bool] = None
    is_registered: Optional[bool] = None
    chat_not_found: Optional[bool] = None

    # ==========================================
    # 4. RANGES (Numbers & Dates)
    # ==========================================

    # Score
    score__gte: Optional[int] = Field(default=None, alias="min_score")
    score__lte: Optional[int] = Field(default=None, alias="max_score")

    counter__gte: Optional[int] = Field(default=None, alias="min_counter")
    counter__lte: Optional[int] = Field(default=None, alias="max_counter")

    # Ban Time (Unix Timestamp)
    ban_time__gte: Optional[int] = Field(default=None, alias="min_ban_time")
    ban_time__lte: Optional[int] = Field(default=None, alias="max_ban_time")

    # Join Date (Unix Timestamp - BigInteger)
    join_date__gte: Optional[int] = Field(default=None, alias="joined_after_unix")
    join_date__lte: Optional[int] = Field(default=None, alias="joined_before_unix")

    # Hilfen numeric fields
    hilfen_date_join__gte: Optional[int] = Field(default=None, alias="hilfen_joined_after_unix")
    hilfen_date_join__lte: Optional[int] = Field(default=None, alias="hilfen_joined_before_unix")
    hilfen_id__gte: Optional[int] = Field(default=None, alias="min_hilfen_id")
    hilfen_id__lte: Optional[int] = Field(default=None, alias="max_hilfen_id")
    hilfen_all_projects__gte: Optional[int] = Field(default=None, alias="min_hilfen_all_projects")
    hilfen_all_projects__lte: Optional[int] = Field(default=None, alias="max_hilfen_all_projects")
    hilfen_all_projects_done__gte: Optional[int] = Field(default=None, alias="min_hilfen_projects_done")
    hilfen_all_projects_done__lte: Optional[int] = Field(default=None, alias="max_hilfen_projects_done")
    hilfen_limits_time__gte: Optional[int] = Field(default=None, alias="min_hilfen_limits_time")
    hilfen_limits_time__lte: Optional[int] = Field(default=None, alias="max_hilfen_limits_time")

    # DB Timestamps (DateTime objects)
    updated_at__gte: Optional[datetime] = Field(default=None, alias="updated_after")
    updated_at__lte: Optional[datetime] = Field(default=None, alias="updated_before")

    channel_updated_at__gte: Optional[datetime] = Field(default=None, alias="channel_updated_after")
    channel_updated_at__lte: Optional[datetime] = Field(default=None, alias="channel_updated_before")

    # ==========================================
    # 5. NULL CHECKS (IS NULL)
    # ==========================================

    accounting_code__isnull: Optional[bool] = Field(default=None, alias="no_accounting_code")
    counter__isnull: Optional[bool] = Field(default=None, alias="no_counter")

    username__isnull: Optional[bool] = Field(default=None, alias="no_username")
    first_name__isnull: Optional[bool] = Field(default=None, alias="no_first_name")
    last_name__isnull: Optional[bool] = Field(default=None, alias="no_last_name")
    nickname__isnull: Optional[bool] = Field(default=None, alias="no_nickname")

    phone_number__isnull: Optional[bool] = Field(default=None, alias="no_phone_number")
    whatsapp_number__isnull: Optional[bool] = Field(default=None, alias="no_whatsapp_number")
    country__isnull: Optional[bool] = Field(default=None, alias="no_country")

    password__isnull: Optional[bool] = Field(default=None, alias="no_password")
    mode__isnull: Optional[bool] = Field(default=None, alias="no_mode")

    join_date__isnull: Optional[bool] = Field(default=None, alias="no_join_date")
    profile_path__isnull: Optional[bool] = Field(default=None, alias="no_profile_path")

    telegram_message_id__isnull: Optional[bool] = Field(default=None, alias="no_telegram_msg_id")
    group_message_id__isnull: Optional[bool] = Field(default=None, alias="no_group_msg_id")
    public_message_id__isnull: Optional[bool] = Field(default=None, alias="no_public_msg_id")
    public_group_message_id__isnull: Optional[bool] = Field(default=None, alias="no_public_group_msg_id")

    hilfen_id__isnull: Optional[bool] = Field(default=None, alias="no_hilfen_id")
    hilfen_status__isnull: Optional[bool] = Field(default=None, alias="no_hilfen_status")
    hilfen_date_join__isnull: Optional[bool] = Field(default=None, alias="no_hilfen_date_join")
    hilfen_command__isnull: Optional[bool] = Field(default=None, alias="no_hilfen_command")
    hilfen_data__isnull: Optional[bool] = Field(default=None, alias="no_hilfen_data")
    hilfen_id_card_photo__isnull: Optional[bool] = Field(default=None, alias="no_hilfen_id_card_photo")
    hilfen_all_projects__isnull: Optional[bool] = Field(default=None, alias="no_hilfen_all_projects")
    hilfen_all_projects_done__isnull: Optional[bool] = Field(default=None, alias="no_hilfen_all_projects_done")
    hilfen_limits_time__isnull: Optional[bool] = Field(default=None, alias="no_hilfen_limits_time")
    hilfen_message_id__isnull: Optional[bool] = Field(default=None, alias="no_hilfen_msg_id")
    hilfen_group_message_id__isnull: Optional[bool] = Field(default=None, alias="no_hilfen_group_msg_id")

    channel_updated_at__isnull: Optional[bool] = Field(default=None, alias="no_channel_update")

    # ==========================================
    # 6. CONFIG & SORTING
    # ==========================================

    # user_id_updated_at is established when a row is created and normally never
    # changes, making it the most reliable creation-order proxy in this schema.
    order_by: list[str] = ["-user_id_updated_at"]

    class Constants(Filter.Constants):
        model = User

    # ==========================================
    # 7. VALIDATORS
    # ==========================================
    @field_validator(
        "username__ilike", 
        "first_name__ilike", 
        "last_name__ilike", 
        "nickname__ilike", 
        "country__ilike", 
        "phone_number__ilike",
        "whatsapp_number__ilike",
        "profile_path__ilike",
        "accounting_code__ilike",
        "password__ilike",
        "mode__ilike",
        "hilfen_status__ilike",
        "hilfen_command__ilike",
        "hilfen_data__ilike",
        "hilfen_id_card_photo__ilike"
    )
    def make_partial_match(cls, v: Optional[str]):
        """
        Wraps the input string in % to perform a SQL 'LIKE %value%' search.
        """
        if v:
            return f"%{v}%"
        return v
