from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api import openai_proxy
from app.core.config import Settings, get_settings
from app.db.session import get_db_session
from app.main import app


@dataclass(frozen=True)
class FakeHandle:
    trace_id: object
    span_id: object
    started_at: datetime


class StreamingRecorder:
    started = None
    finished = None

    def __init__(self, session, settings) -> None:
        self.session = session
        self.settings = settings

    async def start_span(self, **kwargs):
        StreamingRecorder.started = kwargs
        return FakeHandle(uuid4(), uuid4(), datetime.now(UTC))

    async def finish_span(self, handle, result) -> None:
        StreamingRecorder.finished = result


class FakeStreamContext:
    async def __aexit__(self, exc_type, exc, tb):
        return None


class FakeHttpClient:
    closed = False

    async def aclose(self) -> None:
        self.closed = True


class FakeStreamResponse:
    is_success = True
    status_code = 200
    headers = {"content-type": "text/event-stream"}

    async def aiter_lines(self):
        yield 'data: {"id":"chatcmpl-test","model":"gpt-4o-mini","choices":[{"delta":{"content":"he"}}]}'
        yield ""
        yield 'data: {"id":"chatcmpl-test","model":"gpt-4o-mini","choices":[{"delta":{"content":"llo"}}]}'
        yield ""
        yield 'data: {"id":"chatcmpl-test","model":"gpt-4o-mini","choices":[],"usage":{"prompt_tokens":4,"completion_tokens":2,"total_tokens":6}}'
        yield ""
        yield "data: [DONE]"
        yield ""


class FakeStreamingOpenAIProxyClient:
    forwarded_body = None

    def __init__(self, settings) -> None:
        self.settings = settings

    async def stream_chat_completions(self, *, headers, body):
        FakeStreamingOpenAIProxyClient.forwarded_body = body
        return FakeHttpClient(), FakeStreamResponse(), FakeStreamContext()


async def fake_db_session():
    yield object()


def test_streaming_proxy_forwards_chunks_and_records_usage(monkeypatch) -> None:
    StreamingRecorder.started = None
    StreamingRecorder.finished = None
    FakeStreamingOpenAIProxyClient.forwarded_body = None
    app.dependency_overrides[get_db_session] = fake_db_session
    app.dependency_overrides[get_settings] = lambda: Settings()
    monkeypatch.setattr(openai_proxy, "TraceRecorder", StreamingRecorder)
    monkeypatch.setattr(openai_proxy, "OpenAIProxyClient", FakeStreamingOpenAIProxyClient)

    try:
        with TestClient(app) as client:
            with client.stream(
                "POST",
                "/v1/chat/completions",
                headers={"Authorization": "Bearer test"},
                json={
                    "model": "gpt-4o-mini",
                    "stream": True,
                    "messages": [{"role": "user", "content": "hello"}],
                },
            ) as response:
                content = response.read().decode("utf-8")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "data:" in content
    assert '"content":"he"' in content
    assert FakeStreamingOpenAIProxyClient.forwarded_body["stream_options"] == {"include_usage": True}
    assert StreamingRecorder.started["is_stream"] is True
    assert StreamingRecorder.finished.total_tokens == 6
    assert StreamingRecorder.finished.response_body["choices"][0]["message"]["content"] == "hello"
