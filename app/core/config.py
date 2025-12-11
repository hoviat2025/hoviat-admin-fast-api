from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    DATABASE_URL: str
    APP_MODE: str = "all"
    SECRET_KEY: str  # <--- Crucial for JWT signing
    
    # Auth Config
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Static Tokens
    BOT_API_TOKEN: str
    # ADMIN_API_TOKEN is removed! We don't use static tokens for admins anymore.

    # Telegram Bot Config
    SENDER_BOT_TOKEN: str
    EURO_BOT_TOKEN: str
    TELEGRAM_BASE_URL: str

    # R2 / S3 Configuration
    R2_ENDPOINT_URL: str
    R2_ACCESS_KEY_ID: str
    R2_SECRET_ACCESS_KEY: str
    R2_BUCKET_NAME: str
    
    MAIN_CHANNEL_ID: str = "-1003307384504"
    MAIN_GROUP_ID: str = "-1003436431380"
    PUBLIC_CHANNEL_ID: str = "-1003283701037"
    PUBLIC_GROUP_ID: str = "-1003483024519"
    FORMATTER_WORKER_URL: str = "https://snowy-rain-3f69.safaee1361.workers.dev"
    
    DEFAULT_PROFILE_PICTURE: str = "https://static.vecteezy.com/system/resources/previews/036/280/651/non_2x/default-avatar-profile-icon-social-media-user-image-gray-avatar-icon-blank-profile-silhouette-illustration-vector.jpg"

    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()