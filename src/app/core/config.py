# app/core/config.py
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict



class Settings(BaseSettings):
    DATABASE_URL: str
    OPENROUTER_API_KEY: str
    MODEL_NAME: str 
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    # JWT
    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    REFRESH_TOKEN_EXPIRE_DAYS: int

    # CORS
    ALLOWED_ORIGINS: list[str]

    # App
    APP_NAME: str
    API_V1_STR: str 
    DEBUG: bool

    # Redis
    REDIS_URL: str
    RATE_LIMIT_ENABLED: bool
    CACHE_TTL_DEFAULT: int
    REDIS_PASSWORD: str

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
