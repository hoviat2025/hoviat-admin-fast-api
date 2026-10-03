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

    Security note: the password hash is NOT filterable and NOT returned by the
    response schema. It used to be exposed as both a response field and exact /
    contains / null filters, which let an admin run LIKE probes against bcrypt
    hashes. Nothing needs it, so it is removed rather than merely undocumented.

    `Constants.ordering_allow_list` (below) additionally restricts `order_by` to
    real, sortable columns.
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

    # The library's stock validation only checks `hasattr(model, field_name)`,
    # which ANY class attribute satisfies. That let ?order_by=metadata pass
    # validation and then raise AttributeError inside sort(), surfacing as an
    # unhandled HTTP 500. This validator restricts ordering to real Column
    # objects, so a non-column attribute is rejected as ordinary bad input.
    #
    # Declared on UserFilter (not inside Constants, which is not a Pydantic model)
    # and with check_fields=False, because the library rewrites `order_by` to
    # Optional[str] at request-parsing time and would otherwise reject the
    # annotated list type.
    @field_validator("order_by", mode="before", check_fields=False)
    @classmethod
    def _validate_order_by_columns(cls, value):
        """
        Runs before the library's own validator, on the raw input.

        That matters: the library converts a comma-separated string into a list
        in a `mode="after"` validator, so an "after" check would see one entry
        like "-score,username" instead of two. Splitting here means each column
        is checked individually.

        Accepts a list or a comma-separated string, because a direct
        UserFilter(...) call can supply either.
        """
        if not value:
            return value

        from sqlalchemy import Column
        from sqlalchemy.orm.attributes import InstrumentedAttribute

        if isinstance(value, str):
            entries = [item.strip() for item in value.split(",") if item.strip()]
        else:
            entries = list(value)

        for entry in entries:
            name = entry.replace("-", "").replace("+", "")
            attribute = getattr(User, name, None)
            # A mapped column is an InstrumentedAttribute carrying a Column
            # comparator; anything else on the class (MetaData, a relationship,
            # a plain function) is not orderable.
            comparator = getattr(attribute, "comparator", None)
            is_column = (
                isinstance(attribute, InstrumentedAttribute)
                and comparator is not None
                and isinstance(getattr(comparator, "__clause_element__", lambda: None)(), Column)
            )
            if not is_column:
                raise ValueError(f"{entry} is not an orderable column.")
        return value

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
