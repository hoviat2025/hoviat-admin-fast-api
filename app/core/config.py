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
    TELEGRAM_BOT_TOKEN: str
    TELEGRAM_BASE_URL: str

    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()