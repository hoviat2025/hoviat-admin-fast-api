from typing import Optional
from datetime import datetime
from pydantic import Field, ConfigDict, field_validator
from fastapi_filter.contrib.sqlalchemy import Filter
from app.models.user import User

class UserFilter(Filter):
    """
    Comprehensive Filter for Users.
    Includes support for every column in the users_eurobot table.
    """
    model_config = ConfigDict(
        extra='ignore',       # Allow pagination params (page, size) to pass through
        populate_by_name=True # Allow using both variable names and aliases
    )

    # ==========================================
    # 1. TEXT SEARCH (Partial & Case Insensitive)
    # ==========================================
    # These fields will be auto-wrapped in %...% by the validator below.
    
    username__ilike: Optional[str] = Field(default=None, alias="username")
    first_name__ilike: Optional[str] = Field(default=None, alias="first_name")
    last_name__ilike: Optional[str] = Field(default=None, alias="last_name")
    nickname__ilike: Optional[str] = Field(default=None, alias="nickname")
    country__ilike: Optional[str] = Field(default=None, alias="country")
    phone_number__ilike: Optional[str] = Field(default=None, alias="phone_number")
    whatsapp_number__ilike: Optional[str] = Field(default=None, alias="whatsapp_number")
    profile_path__ilike: Optional[str] = Field(default=None, alias="profile_path")

    # ==========================================
    # 2. EXACT MATCHES (IDs, Codes, Enums)
    # ==========================================
    
    counter: Optional[int] = None
    user_id: Optional[int] = None
    accounting_code: Optional[str] = None
    mode: Optional[str] = None
    
    # Message IDs (Usually exact match is best for IDs)
    telegram_message_id: Optional[str] = None
    group_message_id: Optional[str] = None
    public_message_id: Optional[str] = None
    public_group_message_id: Optional[str] = None

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
    
    # Ban Time
    ban_time__gte: Optional[int] = Field(default=None, alias="min_ban_time")
    
    # Join Date (Unix Timestamp - BigInteger)
    join_date__gte: Optional[int] = Field(default=None, alias="joined_after_unix")
    join_date__lte: Optional[int] = Field(default=None, alias="joined_before_unix")

    # DB Timestamps (DateTime objects)
    updated_at__gte: Optional[datetime] = Field(default=None, alias="updated_after")
    updated_at__lte: Optional[datetime] = Field(default=None, alias="updated_before")
    
    channel_updated_at__gte: Optional[datetime] = Field(default=None, alias="channel_updated_after")
    channel_updated_at__lte: Optional[datetime] = Field(default=None, alias="channel_updated_before")

    # ==========================================
    # 5. NULL CHECKS (IS NULL)
    # ==========================================
    # Use ?no_accounting_code=true to find users with null accounting_code
    
    user_id__isnull: Optional[bool] = Field(default=None, alias="no_user_id")
    accounting_code__isnull: Optional[bool] = Field(default=None, alias="no_accounting_code")
    
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
    
    channel_updated_at__isnull: Optional[bool] = Field(default=None, alias="no_channel_update")

    # ==========================================
    # 6. CONFIG & SORTING
    # ==========================================
    
    order_by: list[str] = ["-counter"]
    
    class Constants(Filter.Constants):
        model = User

    # ==========================================
    # 7. VALIDATORS (Wildcard Injection)
    # ==========================================
    @field_validator(
        "username__ilike", 
        "first_name__ilike", 
        "last_name__ilike", 
        "nickname__ilike", 
        "country__ilike", 
        "phone_number__ilike",
        "whatsapp_number__ilike",
        "profile_path__ilike"
    )
    def make_partial_match(cls, v: Optional[str]):
        """
        Automatically wraps the input string in % to perform a 'Contains' search.
        """
        if v:
            return f"%{v}%"
        return v