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
    anthropic_base_url: str = "https://api.anthropic.com/v1"
    request_timeout_seconds: float = 120.0
    pricing_config_path: str = "config/pricing.example.yaml"

    record_request_body: bool = True
    record_response_body: bool = True
    max_body_bytes: int = 65536
    redact_headers: bool = True

    gateway_api_keys: str = ""
    default_tenant_id: str = "default"

    alerts_enabled: bool = False
    alert_window_minutes: int = 5
    alert_error_rate_threshold: float = 0.2
    alert_min_requests: int = 10
    alert_p95_latency_ms: int = 30000
    alert_cost_spike_multiplier: float = 3.0
    alert_min_cost_usd: float = 1.0
    alert_webhook_url: str | None = None

    @property
    def gateway_api_key_set(self) -> set[str]:
        return {key.strip() for key in self.gateway_api_keys.split(",") if key.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()