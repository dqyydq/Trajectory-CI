from __future__ import annotations

import json
from typing import Any

from app.core.config import Settings

SENSITIVE_HEADER_NAMES = {"authorization", "proxy-authorization", "cookie", "set-cookie", "x-api-key"}


def sanitize_headers(headers: dict[str, str], settings: Settings) -> dict[str, str]:
    if not settings.redact_headers:
        return dict(headers)
    return {
        key: "[REDACTED]" if key.lower() in SENSITIVE_HEADER_NAMES else value
        for key, value in headers.items()
    }


def limit_json_body(value: Any, *, enabled: bool, max_bytes: int) -> Any:
    if not enabled:
        return None

    encoded = json.dumps(value, ensure_ascii=False, default=str).encode("utf-8")
    if len(encoded) <= max_bytes:
        return value

    truncated = encoded[:max_bytes].decode("utf-8", errors="ignore")
    return {
        "_truncated": True,
        "_original_bytes": len(encoded),
        "_max_bytes": max_bytes,
        "preview": truncated,
    }

