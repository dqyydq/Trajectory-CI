from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Span, SpanType, Trace


@dataclass(frozen=True)
class FetchedTrajectory:
    task_id: str
    run_id: str
    traces: list[Trace]
    spans: list[Span]

    @property
    def was_run(self) -> bool:
        return bool(self.traces)

    @property
    def trace_ids(self) -> list[str]:
        return [str(trace.trace_id) for trace in self.traces]


async def fetch_trajectory(session: AsyncSession, *, task_id: str, run_id: str) -> FetchedTrajectory:
    traces = (
        await session.execute(
            select(Trace)
            .where(Trace.eval_task_id == task_id, Trace.eval_run_id == run_id)
            .options(selectinload(Trace.spans))
            .order_by(Trace.started_at.asc())
        )
    ).scalars().all()
    trace_ids: list[UUID] = [trace.trace_id for trace in traces]
    spans: list[Span] = []
    if trace_ids:
        spans = (
            await session.execute(
                select(Span)
                .where(Span.trace_id.in_(trace_ids), Span.span_type == SpanType.llm_call)
                .order_by(Span.started_at.asc())
            )
        ).scalars().all()
    return FetchedTrajectory(task_id=task_id, run_id=run_id, traces=list(traces), spans=list(spans))