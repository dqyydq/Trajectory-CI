from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_ignore_empty=True,
        extra="ignore",
    )

    project_name: str = "Agent Observability Gateway"
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/agent_observability",
        description="Async SQLAlchemy database URL.",
    )
    dashboard_database_url: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost:5432/agent_observability",
        description="Sync PostgreSQL URL for Streamlit dashboard queries.",
    )
    openai_base_url: str = "https://api.openai.com/v1"
    request_timeout_seconds: float = 120.0
    pricing_config_path: str = "config/pricing.example.yaml"

    record_request_body: bool = True
    record_response_body: bool = True
    max_body_bytes: int = 65536
    redact_headers: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()


