from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    # --- Infrastructure (Must come from Env) ---
    DATABASE_URL: str
    
    # --- App Config ---
    APP_MODE: str = "dev" # Default to dev if not set
    SECRET_KEY: str       # Crucial: Application will fail to start if missing
    
    # --- Auth Config (Constants/Business Logic can stay here) ---
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080 
    ALGORITHM: str = "HS256"
    
    BOT_API_TOKEN: str

    # --- Telegram Config ---
    SENDER_BOT_TOKEN: str
    EURO_BOT_TOKEN: str
    TELEGRAM_BASE_URL: str = "https://api.telegram.org" # Good default, override in .env if needed

    # --- R2 / S3 Configuration ---
    R2_ENDPOINT_URL: str
    R2_ACCESS_KEY_ID: str
    R2_SECRET_ACCESS_KEY: str
    R2_BUCKET_NAME: str
    
    # --- IDs & External URLs (Moved from hardcoded to Type definitions) ---
    # We define them as str without defaults so Pydantic forces us to put them in .env
    # This prevents accidentally using Production IDs in a Dev environment.
    MAIN_CHANNEL_ID: str 
    MAIN_GROUP_ID: str
    PUBLIC_CHANNEL_ID: str 
    PUBLIC_GROUP_ID: str
    FORMATTER_WORKER_URL: str

    # --- Assets (Can stay hardcoded if they rarely change) ---
    DEFAULT_PROFILE_PICTURE: str = "https://static.vecteezy.com/system/resources/previews/036/280/651/non_2x/default-avatar-profile-icon-social-media-user-image-gray-avatar-icon-blank-profile-silhouette-illustration-vector.jpg"

    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        extra="ignore" # Good practice: ignore extra fields in .env that aren't in this class
    )

settings = Settings()