from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

import httpx
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


class FakeRecorder:
    finished = None

    def __init__(self, session, settings) -> None:
        self.session = session
        self.settings = settings

    async def start_span(self, **kwargs):
        return FakeHandle(uuid4(), uuid4(), datetime.now(UTC))

    async def finish_span(self, handle, result) -> None:
        FakeRecorder.finished = result


class FakeOpenAIProxyClient:
    def __init__(self, settings) -> None:
        self.settings = settings

    async def post_chat_completions(self, *, headers, body):
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-test",
                "model": body["model"],
                "choices": [{"message": {"role": "assistant", "content": "hi"}}],
                "usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
            },
        )


async def fake_db_session():
    yield object()


def test_non_streaming_proxy_records_success(monkeypatch) -> None:
    FakeRecorder.finished = None
    app.dependency_overrides[get_db_session] = fake_db_session
    app.dependency_overrides[get_settings] = lambda: Settings()
    monkeypatch.setattr(openai_proxy, "TraceRecorder", FakeRecorder)
    monkeypatch.setattr(openai_proxy, "OpenAIProxyClient", FakeOpenAIProxyClient)

    try:
        with TestClient(app) as client:
            response = client.post(
                "/v1/chat/completions",
                headers={"Authorization": "Bearer test"},
                json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "hello"}]},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["choices"][0]["message"]["content"] == "hi"
    assert FakeRecorder.finished is not None
    assert FakeRecorder.finished.total_tokens == 5
    assert FakeRecorder.finished.status.value == "success"
