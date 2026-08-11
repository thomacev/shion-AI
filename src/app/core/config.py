# app/core/config.py
from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str
    REDIS_URL: str
    CELERY_BROKER_URL: str
    GEMINI_API_KEY: str
    SECRET_KEY: str

    POSTGRES_USER: Optional[str] = None
    POSTGRES_PASSWORD: Optional[str] = None
    POSTGRES_DB: Optional[str] = None
    DATABASE_TEST_URL: Optional[str] = None
    REDIS_PASSWORD: Optional[str] = None

    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALLOWED_ORIGINS: list[str] = ["*"]

    APP_NAME: str = "Shion AI Assistant"
    DEBUG: bool = False
    API_V1_STR: str = "/api/v1"

    MODEL_NAME: str = "gemini-1.5-flash"
    LLM_MAX_TOKENS: int = 2048
    LLM_TEMPERATURE: float = 0.7
    EMBEDDING_MODEL: str = "text-embedding-004"
    EMBEDDING_DIM: int = 768

    RATE_LIMIT_ENABLED: bool = True
    CACHE_TTL_DEFAULT: int = 300

    MAX_DOCUMENT_SIZE_MB: int = 10

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Singleton to avoid reloading settings multiple times."""
    return Settings()


settings = get_settings()