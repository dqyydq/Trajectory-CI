from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import Settings
from app.db.models import EvalReport, EvalTaskResult, Span, SpanStatus, SpanType, Trace
from eval.compare.runner import compare_runs
from eval.schemas import JudgeResult

pytestmark = pytest.mark.asyncio


class FakeScorer:
    def score(self, *, task, trajectory):
        return JudgeResult(score=4, reason=f"judged {task.task_id}")


def _make_session_factory():
    engine = create_async_engine(Settings().database_url, poolclass=NullPool)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def _database_available(session_factory) -> bool:
    try:
        async with session_factory() as session:
            await session.execute(select(1))
        return True
    except (SQLAlchemyError, OSError):
        return False


async def test_compare_persists_not_run_result() -> None:
    engine, session_factory = _make_session_factory()
    db_available = False
    task_id = f"task-{uuid4()}"
    temp_dir = Path(".test_tmp")
    temp_dir.mkdir(exist_ok=True)
    task_set_path = temp_dir / f"tasks-{uuid4()}.yaml"
    try:
        db_available = await _database_available(session_factory)
        if not db_available:
            pytest.skip("PostgreSQL is not available")
        task_set_path.write_text(
            f"""
tasks:
  - task_id: "{task_id}"
    description: "desc"
    input: "input"
    checks:
      - type: response_contains
        keyword: "done"
""",
            encoding="utf-8",
        )
        async with session_factory() as session:
            trace = Trace(eval_task_id=task_id, eval_run_id="v1")
            session.add(trace)
            await session.flush()
            session.add(
                Span(
                    trace_id=trace.trace_id,
                    span_type=SpanType.llm_call,
                    model="gpt-test",
                    response_body={"choices": [{"message": {"content": "done"}}]},
                    status=SpanStatus.success,
                    is_stream=False,
                    started_at=trace.started_at,
                    ended_at=trace.started_at,
                )
            )
            await session.commit()

        async with session_factory() as session:
            result = await compare_runs(
                session=session,
                task_set_path=str(task_set_path),
                task_set_name="mini",
                run_id_a="v1",
                run_id_b="v2",
                scorer=FakeScorer(),
            )

        assert result.summary["regressed_count"] == 1
        detail = result.details[task_id]
        assert detail.run_a.status == "judged"
        assert detail.run_b.status == "not_run"
        assert detail.diff.regressed is True

        async with session_factory() as session:
            reports = (await session.execute(select(EvalReport).where(EvalReport.report_id == result.report_id))).scalars().all()
            rows = (await session.execute(select(EvalTaskResult).where(EvalTaskResult.report_id == result.report_id))).scalars().all()
        assert len(reports) == 1
        assert len(rows) == 1
        assert rows[0].detail["run_b"]["status"] == "not_run"
    finally:
        if db_available:
            async with session_factory() as session:
                trace_ids = (await session.execute(select(Trace.trace_id).where(Trace.eval_task_id == task_id))).scalars().all()
                if trace_ids:
                    await session.execute(delete(Span).where(Span.trace_id.in_(trace_ids)))
                    await session.execute(delete(Trace).where(Trace.trace_id.in_(trace_ids)))
                await session.execute(delete(EvalReport).where(EvalReport.task_set_name == "mini"))
                await session.commit()
        await engine.dispose()
