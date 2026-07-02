from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.core.config import Settings
from app.db.models import SpanStatus
from app.protocols.anthropic import aggregate_anthropic_stream, anthropic_usage, parse_anthropic_sse_line
from app.protocols.common import enforce_gateway_auth, tenant_id_from_request, upstream_headers


def _request(headers: dict[str, str]):
    return SimpleNamespace(headers=headers)


def test_gateway_auth_allows_requests_when_disabled() -> None:
    enforce_gateway_auth(_request({}), Settings(gateway_api_keys=""))


def test_gateway_auth_rejects_missing_or_invalid_key() -> None:
    settings = Settings(gateway_api_keys="key-a,key-b")

    with pytest.raises(HTTPException) as exc_info:
        enforce_gateway_auth(_request({}), settings)
    assert exc_info.value.status_code == 401

    with pytest.raises(HTTPException):
        enforce_gateway_auth(_request({"X-Gateway-Api-Key": "wrong"}), settings)

    enforce_gateway_auth(_request({"X-Gateway-Api-Key": "key-a"}), settings)


def test_tenant_id_defaults_and_strips_header() -> None:
    settings = Settings(default_tenant_id="default-tenant")

    assert tenant_id_from_request(_request({}), settings) == "default-tenant"
    assert tenant_id_from_request(_request({"X-Tenant-Id": " tenant-a "}), settings) == "tenant-a"


def test_upstream_headers_strip_gateway_only_headers() -> None:
    headers = upstream_headers(
        {
            "Authorization": "Bearer upstream",
            "Anthropic-Version": "2023-06-01",
            "X-Gateway-Api-Key": "gateway-key",
            "X-Tenant-Id": "tenant-a",
            "X-Session-Id": "session-a",
            "Connection": "keep-alive",
        }
    )

    assert headers == {"Authorization": "Bearer upstream", "Anthropic-Version": "2023-06-01"}


def test_anthropic_usage_extracts_total_tokens() -> None:
    assert anthropic_usage({"usage": {"input_tokens": 5, "output_tokens": 7}}) == (5, 7, 12)
    assert anthropic_usage({}) == (None, None, None)


def test_anthropic_stream_aggregation_best_effort() -> None:
    events = [
        parse_anthropic_sse_line(b'data: {"type":"message_start","message":{"id":"msg_1","model":"claude-test","usage":{"input_tokens":4}}}'),
        parse_anthropic_sse_line(b'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"he"}}'),
        parse_anthropic_sse_line(b'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"llo"}}'),
        parse_anthropic_sse_line(b'data: {"type":"message_delta","usage":{"output_tokens":2}}'),
    ]
    response = aggregate_anthropic_stream([event for event in events if event is not None])

    assert response["id"] == "msg_1"
    assert response["model"] == "claude-test"
    assert response["content"][0]["text"] == "hello"
    assert response["usage"] == {"input_tokens": 4, "output_tokens": 2}
    assert anthropic_usage(response) == (4, 2, 6)