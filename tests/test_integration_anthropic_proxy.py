from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

import httpx
from fastapi.testclient import TestClient

from app.api import anthropic_proxy
from app.core.config import Settings, get_settings
from app.db.session import get_db_session
from app.main import app


@dataclass(frozen=True)
class FakeHandle:
    trace_id: object
    span_id: object
    started_at: datetime


class FakeRecorder:
    started = None
    finished = None

    def __init__(self, session, settings) -> None:
        self.session = session
        self.settings = settings

    async def start_span(self, **kwargs):
        FakeRecorder.started = kwargs
        return FakeHandle(uuid4(), uuid4(), datetime.now(UTC))

    async def finish_span(self, handle, result) -> None:
        FakeRecorder.finished = result


class FakeAnthropicProxyClient:
    forwarded_headers = None

    def __init__(self, settings) -> None:
        self.settings = settings

    async def post_messages(self, *, headers, body):
        FakeAnthropicProxyClient.forwarded_headers = headers
        return httpx.Response(
            200,
            json={
                "id": "msg_1",
                "type": "message",
                "model": body["model"],
                "content": [{"type": "text", "text": "hi"}],
                "usage": {"input_tokens": 3, "output_tokens": 2},
            },
        )


class FakeStreamContext:
    async def __aexit__(self, exc_type, exc, tb):
        return None


class FakeHttpClient:
    async def aclose(self) -> None:
        return None


class FakeStreamResponse:
    is_success = True
    status_code = 200
    headers = {"content-type": "text/event-stream"}

    async def aiter_lines(self):
        yield 'event: message_start'
        yield 'data: {"type":"message_start","message":{"id":"msg_1","model":"claude-test","usage":{"input_tokens":4}}}'
        yield ''
        yield 'event: content_block_delta'
        yield 'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"he"}}'
        yield ''
        yield 'event: content_block_delta'
        yield 'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"llo"}}'
        yield ''
        yield 'event: message_delta'
        yield 'data: {"type":"message_delta","usage":{"output_tokens":2}}'
        yield ''


class FakeStreamingAnthropicProxyClient:
    def __init__(self, settings) -> None:
        self.settings = settings

    async def stream_messages(self, *, headers, body):
        return FakeHttpClient(), FakeStreamResponse(), FakeStreamContext()


async def fake_db_session():
    yield object()


def test_anthropic_non_streaming_proxy_records_success(monkeypatch) -> None:
    FakeRecorder.started = None
    FakeRecorder.finished = None
    FakeAnthropicProxyClient.forwarded_headers = None
    app.dependency_overrides[get_db_session] = fake_db_session
    app.dependency_overrides[get_settings] = lambda: Settings(gateway_api_keys="gateway-key")
    monkeypatch.setattr(anthropic_proxy, "TraceRecorder", FakeRecorder)
    monkeypatch.setattr(anthropic_proxy, "AnthropicProxyClient", FakeAnthropicProxyClient)

    try:
        with TestClient(app) as client:
            response = client.post(
                "/v1/messages",
                headers={
                    "X-Gateway-Api-Key": "gateway-key",
                    "X-Tenant-Id": "tenant-a",
                    "X-Session-Id": "session-a",
                    "Anthropic-Version": "2023-06-01",
                    "X-Api-Key": "anthropic-upstream-key",
                },
                json={"model": "claude-3-5-sonnet-latest", "max_tokens": 64, "messages": [{"role": "user", "content": "hi"}]},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["content"][0]["text"] == "hi"
    assert FakeRecorder.started["tenant_id"] == "tenant-a"
    assert FakeRecorder.finished.total_tokens == 5
    assert FakeRecorder.finished.status.value == "success"


def test_anthropic_streaming_proxy_records_success(monkeypatch) -> None:
    FakeRecorder.started = None
    FakeRecorder.finished = None
    app.dependency_overrides[get_db_session] = fake_db_session
    app.dependency_overrides[get_settings] = lambda: Settings()
    monkeypatch.setattr(anthropic_proxy, "TraceRecorder", FakeRecorder)
    monkeypatch.setattr(anthropic_proxy, "AnthropicProxyClient", FakeStreamingAnthropicProxyClient)

    try:
        with TestClient(app) as client:
            with client.stream(
                "POST",
                "/v1/messages",
                json={"model": "claude-3-5-sonnet-latest", "stream": True, "max_tokens": 64, "messages": [{"role": "user", "content": "hi"}]},
            ) as response:
                content = response.read().decode("utf-8")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "message_start" in content
    assert FakeRecorder.started["is_stream"] is True
    assert FakeRecorder.finished.total_tokens == 6
    assert FakeRecorder.finished.response_body["content"][0]["text"] == "hello"