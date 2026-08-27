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

    # Secret required by the internal server scheduler when triggering cron sync.
    # Keep this separate from JWT, admin, and bot credentials.
    CRON_SYNC_SECRET: str
    
    # --- Authentication & JWT Settings ---
    # Token expiration time (defaulting to 10080 minutes / 7 days)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080 
    # Encryption algorithm used for JWT signing
    ALGORITHM: str = "HS256"
    
    # --- Telegram Integration ---
    # API tokens for various bot instances
    BOT_API_TOKEN: str
    HILFEN_API_TOKEN: str
    SENDER_BOT_TOKEN: str
    EURO_BOT_TOKEN: str
    HILFEN_BOT_TOKEN: str
    
    # Base endpoint for Telegram Bot API requests
    TELEGRAM_BASE_URL: str = "https://api.telegram.org"

    # --- SNS / User Panel ---
    # Shared secret the login-bot worker must present as Bearer when calling
    # request-login. Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"
    LOGIN_BOT_API_SECRET: str
    # Telegram (BotFather) token of the SNS login bot. This is the bot that
    # issues website login codes and can resolve new users' profile photos via
    # getChat. It is NOT the same credential as LOGIN_BOT_API_SECRET (which is
    # how the worker authenticates against this API).
    SNS_LOGIN_BOT_TOKEN: str
    # Base URL prefix used to assemble absolute profile picture URLs.
    PROFILE_MEDIA_URL: str = ""
    # Maximum age (seconds) of the Telegram auth_date before login is rejected.
    TELEGRAM_LOGIN_MAX_AGE_SECONDS: int = 86400
    # Lifetime of bot-issued SNS login tokens (user types token into website).
    LOGIN_TOKEN_TTL_SECONDS: int = 300

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
