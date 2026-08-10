from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Civic Accountability Platform"
    app_env: str = "development"
    app_debug: bool = True
    database_url: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost:5432/civic_platform",
        alias="DATABASE_URL",
    )
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4.1-mini", alias="OPENAI_MODEL")
    backend_cors_origins: str = Field(
        default="http://localhost:3000",
        alias="BACKEND_CORS_ORIGINS",
    )
    ingestion_user_agent: str = Field(
        default="civic-platform/0.1 (+https://example.com)",
        alias="INGESTION_USER_AGENT",
    )
    default_jurisdiction: str = Field(default="ca", alias="DEFAULT_JURISDICTION")
    default_chamber: str = Field(default="house", alias="DEFAULT_CHAMBER")

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.backend_cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
