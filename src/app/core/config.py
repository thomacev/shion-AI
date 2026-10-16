# app/core/config.py
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str
    REDIS_URL: str
    CELERY_BROKER_URL: str
    GEMINI_API_KEY: str
    SECRET_KEY: str

    POSTGRES_USER: str | None = None
    POSTGRES_PASSWORD: str | None = None
    POSTGRES_DB: str | None = None
    DATABASE_TEST_URL: str | None = None
    REDIS_PASSWORD: str | None = None

    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALLOWED_ORIGINS: list[str] = ["*"]

    APP_NAME: str = "Shion AI Assistant"
    DEBUG: bool = False
    API_V1_STR: str = "/api/v1"

    MODEL_NAME: str = Field(min_length=1)
    LLM_MAX_TOKENS: int = Field(default=2048, ge=1)
    LLM_TEMPERATURE: float = 0.7
    EMBEDDING_MODEL: str = Field(min_length=1)
    EMBEDDING_DIM: int = Field(default=1536, ge=1536, le=1536)
    EMBEDDING_BATCH_SIZE: int = Field(default=64, ge=1, le=100)
    PROVIDER_TIMEOUT_SECONDS: int = Field(default=60, ge=1, le=120)
    CHAT_TIMEOUT_SECONDS: int = Field(default=150, ge=1, le=300)
    MAX_MESSAGE_CHARS: int = Field(default=8000, ge=1)
    MAX_PROMPT_TOKENS: int = Field(default=16000, ge=1)

    RATE_LIMIT_ENABLED: bool = True
    CACHE_TTL_DEFAULT: int = 300

    MAX_DOCUMENT_SIZE_MB: int = Field(default=10, ge=1, le=100)
    MAX_DOCUMENT_PAGES: int = Field(default=500, ge=1)
    MAX_EXTRACTED_CHARS: int = Field(default=2000000, ge=1)
    DOCUMENT_TIMEOUT_SECONDS: int = Field(default=300, ge=10, le=600)
    DOCUMENT_MAX_ATTEMPTS: int = Field(default=4, ge=1, le=10)
    DOCUMENT_RECOVERY_SECONDS: int = Field(default=30, ge=5)
    RAG_MAX_DISTANCE: float = 0.5

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
