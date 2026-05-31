from pydantic_settings import BaseSettings, SettingsConfigDict
import os

class Settings(BaseSettings):
    PROJECT_NAME: str = "IT Admin System"
    VERSION: str = "0.1.0"
    ENVIRONMENT: str = "local"
    MONGO_URI: str
    DB_NAME: str = "it_admin_db"
    SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    CRYPTO_KEY: str
    FRONTEND_URL: str = "http://127.0.0.1:3000"

    # SMTP (по умолчанию Gmail, переключается через .env.local)
    SMTP_HOST:    str = "smtp.gmail.com"
    SMTP_PORT:    int = 587
    SMTP_LOGIN:   str = ""   # твой gmail
    SMTP_KEY:     str = ""   # App Password (16 символов из настроек Google)
    SENDER_EMAIL: str = ""
    SENDER_NAME:  str = "IT Admin System"

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    model_config = SettingsConfigDict(
        env_file=".env.local" if os.getenv("ENVIRONMENT") != "production" else ".env.prod",
        case_sensitive=True
    )

settings = Settings()