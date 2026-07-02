from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.db.models import Span, SpanStatus
from app.tracing.recorder import TraceRecorder
from app.tracing.schemas import SpanHandle, SpanResult


class FakeSession:
    def __init__(self) -> None:
        self.added = []
        self.executed = []
        self.commits = 0

    def add(self, obj) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        return None

    async def execute(self, statement):
        self.executed.append(statement)

    async def commit(self) -> None:
        self.commits += 1


@pytest.mark.asyncio
async def test_start_span_inserts_in_progress_span(monkeypatch) -> None:
    session = FakeSession()
    recorder = TraceRecorder(session, Settings())
    trace_id = uuid4()

    async def fake_get_or_create_trace(*, session_id, started_at, eval_task_id, eval_run_id, tenant_id):
        return trace_id

    monkeypatch.setattr(recorder, "_get_or_create_trace", fake_get_or_create_trace)

    handle = await recorder.start_span(
        session_id="session-a",
        model="gpt-4o-mini",
        request_body={"model": "gpt-4o-mini"},
        is_stream=False,
    )

    assert handle.trace_id == trace_id
    assert len(session.added) == 1
    span = session.added[0]
    assert isinstance(span, Span)
    assert span.status == SpanStatus.in_progress
    assert span.span_type.value == "llm_call"
    assert span.model == "gpt-4o-mini"
    assert session.commits == 1


@pytest.mark.asyncio
async def test_finish_span_updates_span_and_trace() -> None:
    session = FakeSession()
    recorder = TraceRecorder(session, Settings())
    handle = SpanHandle(trace_id=uuid4(), span_id=uuid4(), started_at=datetime.now(UTC))

    await recorder.finish_span(
        handle,
        SpanResult(
            status=SpanStatus.success,
            response_body={"usage": {"total_tokens": 3}},
            prompt_tokens=1,
            completion_tokens=2,
            total_tokens=3,
            cost_usd=Decimal("0.000001"),
        ),
    )

    assert len(session.executed) == 2
    assert session.commits == 1
