from __future__ import annotations

from decimal import Decimal
from typing import Any

from fastapi import HTTPException, Request

from app.core.config import Settings
from app.cost.calculator import CostCalculator
from app.cost.pricing import PricingTable

HOP_BY_HOP_HEADERS = {
    "connection",
    "content-length",
    "host",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}

GATEWAY_ONLY_HEADERS = {
    "x-gateway-api-key",
    "x-tenant-id",
    "x-session-id",
    "x-eval-task-id",
    "x-eval-run-id",
    "x-span-type",
}

RESPONSE_EXCLUDED_HEADERS = {"content-length", "content-encoding", "transfer-encoding", "connection"}


def upstream_headers(headers: dict[str, str]) -> dict[str, str]:
    excluded = HOP_BY_HOP_HEADERS | GATEWAY_ONLY_HEADERS
    return {key: value for key, value in headers.items() if key.lower() not in excluded}


def response_headers(headers: dict[str, str]) -> dict[str, str]:
    return {key: value for key, value in headers.items() if key.lower() not in RESPONSE_EXCLUDED_HEADERS}


def enforce_gateway_auth(request: Request, settings: Settings) -> None:
    allowed_keys = settings.gateway_api_key_set
    if not allowed_keys:
        return
    supplied = request.headers.get("X-Gateway-Api-Key")
    if supplied not in allowed_keys:
        raise HTTPException(status_code=401, detail="Invalid or missing gateway API key")


def tenant_id_from_request(request: Request, settings: Settings) -> str:
    tenant_id = request.headers.get("X-Tenant-Id") or settings.default_tenant_id
    return tenant_id.strip() or settings.default_tenant_id


def calculate_cost(
    *,
    settings: Settings,
    model: str | None,
    prompt_tokens: int | None,
    completion_tokens: int | None,
) -> Decimal | None:
    return CostCalculator(PricingTable.from_yaml(settings.pricing_config_path)).calculate(
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
    )


def parse_span_type(raw_value: str | None, default: Any) -> Any:
    enum_cls = type(default)
    try:
        return enum_cls(raw_value or default.value)
    except ValueError:
        return default
