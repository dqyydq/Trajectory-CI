from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

import httpx
from fastapi.testclient import TestClient

from app.api import openai_proxy
from app.core.config import Settings, get_settings
from app.db.models import SpanType
from app.db.session import get_db_session
from app.main import app


@dataclass(frozen=True)
class FakeHandle:
    trace_id: object
    span_id: object
    started_at: datetime


class HeaderRecorder:
    started = None

    def __init__(self, session, settings) -> None:
        self.session = session
        self.settings = settings

    async def start_span(self, **kwargs):
        HeaderRecorder.started = kwargs
        return FakeHandle(uuid4(), uuid4(), datetime.now(UTC))

    async def finish_span(self, handle, result) -> None:
        return None


class FakeOpenAIProxyClient:
    def __init__(self, settings) -> None:
        self.settings = settings

    async def post_chat_completions(self, *, headers, body):
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"role": "assistant", "content": "ok"}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            },
        )


async def fake_db_session():
    yield object()


def test_proxy_passes_eval_headers_to_recorder(monkeypatch) -> None:
    HeaderRecorder.started = None
    app.dependency_overrides[get_db_session] = fake_db_session
    app.dependency_overrides[get_settings] = lambda: Settings()
    monkeypatch.setattr(openai_proxy, "TraceRecorder", HeaderRecorder)
    monkeypatch.setattr(openai_proxy, "OpenAIProxyClient", FakeOpenAIProxyClient)

    try:
        with TestClient(app) as client:
            response = client.post(
                "/v1/chat/completions",
                headers={
                    "Authorization": "Bearer test",
                    "X-Eval-Task-Id": "task-a",
                    "X-Eval-Run-Id": "v2",
                    "X-Span-Type": "llm_judge",
                    "X-Tenant-Id": "tenant-eval",
                },
                json={"model": "gpt-test", "messages": [{"role": "user", "content": "hi"}]},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert HeaderRecorder.started["eval_task_id"] == "task-a"
    assert HeaderRecorder.started["eval_run_id"] == "v2"
    assert HeaderRecorder.started["span_type"] == SpanType.llm_judge
    assert HeaderRecorder.started["tenant_id"] == "tenant-eval"