from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    """
    Application settings and environment variables.
    
    This class handles the validation and loading of configuration values 
    from environment variables and the .env file.
    """

    # --- Database Configuration ---
    # Full SQLAlchemy/PostgreSQL connection URI
    DATABASE_URL: str
    
    # --- Application Environment ---
    # Defines the runtime environment (e.g., "dev", "prod", "test")
    APP_MODE: str = "dev"
    
    # Secret key used for cryptographic signing and security hashes
    SECRET_KEY: str
    
    # --- Authentication & JWT Settings ---
    # Token expiration time (defaulting to 10080 minutes / 7 days)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080 
    # Encryption algorithm used for JWT signing
    ALGORITHM: str = "HS256"
    
    # --- Telegram Integration ---
    # API tokens for various bot instances
    BOT_API_TOKEN: str
    SENDER_BOT_TOKEN: str
    EURO_BOT_TOKEN: str
    HILFEN_BOT_TOKEN: str
    
    # Base endpoint for Telegram Bot API requests
    TELEGRAM_BASE_URL: str = "https://api.telegram.org"

    # --- Cloud Storage (R2/S3 Compatible) ---
    R2_ENDPOINT_URL: str
    R2_ACCESS_KEY_ID: str
    R2_SECRET_ACCESS_KEY: str
    R2_BUCKET_NAME: str
    
    # --- Channel & Group Identifiers ---
    # Unique Telegram IDs for routing messages and permissions
    MAIN_CHANNEL_ID: str 
    MAIN_GROUP_ID: str
    PUBLIC_CHANNEL_ID: str 
    PUBLIC_GROUP_ID: str
    HILFEN_CHANNEL_ID: str 
    HILFEN_GROUP_ID: str
    
    # Internal service URL for the formatting worker
    FORMATTER_WORKER_URL: str

    # --- UI & Static Assets ---
    # Default image URL used for users without a profile picture
    DEFAULT_PROFILE_PICTURE: str = "https://static.vecteezy.com/system/resources/previews/036/280/651/non_2x/default-avatar-profile-icon-social-media-user-image-gray-avatar-icon-blank-profile-silhouette-illustration-vector.jpg"

    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        # Discards additional variables found in .env not defined in this class
        extra="ignore" 
    )

# Global settings instance
settings = Settings()