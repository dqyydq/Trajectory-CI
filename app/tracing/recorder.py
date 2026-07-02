from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.models import Span, SpanStatus, SpanType, Trace
from app.tracing.sanitizer import limit_json_body
from app.tracing.schemas import SpanHandle, SpanResult


class TraceRecorder:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings

    async def start_span(
        self,
        *,
        session_id: str | None,
        model: str | None,
        request_body: Any,
        is_stream: bool,
        parent_span_id: UUID | None = None,
    ) -> SpanHandle:
        started_at = datetime.now(UTC)
        trace_id = await self._get_or_create_trace(session_id=session_id, started_at=started_at)
        span = Span(
            trace_id=trace_id,
            parent_span_id=parent_span_id,
            span_type=SpanType.llm_call,
            model=model,
            request_body=limit_json_body(
                request_body,
                enabled=self.settings.record_request_body,
                max_bytes=self.settings.max_body_bytes,
            ),
            status=SpanStatus.in_progress,
            is_stream=is_stream,
            started_at=started_at,
        )
        self.session.add(span)
        await self.session.commit()
        return SpanHandle(trace_id=trace_id, span_id=span.span_id, started_at=started_at)

    async def finish_span(self, handle: SpanHandle, result: SpanResult) -> None:
        ended_at = datetime.now(UTC)
        latency_ms = int((ended_at - handle.started_at).total_seconds() * 1000)
        response_body = limit_json_body(
            result.response_body,
            enabled=self.settings.record_response_body,
            max_bytes=self.settings.max_body_bytes,
        )
        await self.session.execute(
            update(Span)
            .where(Span.span_id == handle.span_id)
            .values(
                response_body=response_body,
                prompt_tokens=result.prompt_tokens,
                completion_tokens=result.completion_tokens,
                total_tokens=result.total_tokens,
                cost_usd=result.cost_usd,
                latency_ms=latency_ms,
                status=result.status,
                error_message=result.error_message,
                ended_at=ended_at,
            )
        )
        await self.session.execute(
            update(Trace)
            .where(Trace.trace_id == handle.trace_id)
            .values(ended_at=ended_at)
        )
        await self.session.commit()

    async def _get_or_create_trace(self, *, session_id: str | None, started_at: datetime) -> UUID:
        if session_id is None:
            trace = Trace(started_at=started_at)
            self.session.add(trace)
            await self.session.flush()
            return trace.trace_id

        statement = (
            insert(Trace)
            .values(session_id=session_id, started_at=started_at)
            .on_conflict_do_update(
                index_elements=[Trace.session_id],
                index_where=Trace.session_id.is_not(None),
                set_={"session_id": session_id},
            )
            .returning(Trace.trace_id)
        )
        result = await self.session.execute(statement)
        return result.scalar_one()


