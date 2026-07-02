from app.core.config import Settings
from app.tracing.sanitizer import limit_json_body, sanitize_headers


def test_sanitize_headers_redacts_authorization() -> None:
    settings = Settings(redact_headers=True)

    assert sanitize_headers({"Authorization": "Bearer secret", "X-Test": "ok"}, settings)["Authorization"] == "[REDACTED]"


def test_limit_json_body_truncates_large_payload() -> None:
    result = limit_json_body({"text": "x" * 100}, enabled=True, max_bytes=20)

    assert result["_truncated"] is True

