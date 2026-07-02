from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import Settings
from app.db.models import Span, SpanStatus, Trace
from app.tracing.recorder import TraceRecorder

pytestmark = pytest.mark.asyncio


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


async def _cleanup(session_factory, session_id: str) -> None:
    async with session_factory() as session:
        trace_ids = (await session.execute(select(Trace.trace_id).where(Trace.session_id == session_id))).scalars().all()
        if trace_ids:
            await session.execute(delete(Span).where(Span.trace_id.in_(trace_ids)))
            await session.execute(delete(Trace).where(Trace.trace_id.in_(trace_ids)))
            await session.commit()


async def test_concurrent_start_span_reuses_one_trace_for_session_id() -> None:
    engine, session_factory = _make_session_factory()
    try:
        if not await _database_available(session_factory):
            pytest.skip("PostgreSQL is not available")

        session_id = f"concurrency-{uuid4()}"
        settings = Settings()

        async def start_one(index: int):
            async with session_factory() as session:
                recorder = TraceRecorder(session, settings)
                return await recorder.start_span(
                    session_id=session_id,
                    model="gpt-4o-mini",
                    request_body={"model": "gpt-4o-mini", "index": index},
                    is_stream=False,
                )

        try:
            handles = await asyncio.gather(*(start_one(i) for i in range(12)))

            async with session_factory() as session:
                trace_count = await session.scalar(
                    select(func.count()).select_from(Trace).where(Trace.session_id == session_id)
                )
                span_count = await session.scalar(
                    select(func.count())
                    .select_from(Span)
                    .join(Trace, Trace.trace_id == Span.trace_id)
                    .where(Trace.session_id == session_id)
                )

            assert trace_count == 1
            assert span_count == 12
            assert len({handle.trace_id for handle in handles}) == 1
        finally:
            await _cleanup(session_factory, session_id)
    finally:
        await engine.dispose()


async def test_started_span_remains_in_progress_if_not_finished() -> None:
    engine, session_factory = _make_session_factory()
    try:
        if not await _database_available(session_factory):
            pytest.skip("PostgreSQL is not available")

        session_id = f"crash-{uuid4()}"
        try:
            async with session_factory() as session:
                recorder = TraceRecorder(session, Settings())
                handle = await recorder.start_span(
                    session_id=session_id,
                    model="gpt-4o-mini",
                    request_body={"model": "gpt-4o-mini"},
                    is_stream=False,
                )

            async with session_factory() as session:
                span = await session.get(Span, handle.span_id)

            assert span is not None
            assert span.status == SpanStatus.in_progress
            assert span.ended_at is None
            assert span.response_body is None
        finally:
            await _cleanup(session_factory, session_id)
    finally:
        await engine.dispose()


async def test_start_span_persists_tenant_id() -> None:
    engine, session_factory = _make_session_factory()
    try:
        if not await _database_available(session_factory):
            pytest.skip("PostgreSQL is not available")

        session_id = f"tenant-{uuid4()}"
        try:
            async with session_factory() as session:
                recorder = TraceRecorder(session, Settings())
                await recorder.start_span(
                    session_id=session_id,
                    tenant_id="tenant-a",
                    model="gpt-4o-mini",
                    request_body={"model": "gpt-4o-mini"},
                    is_stream=False,
                )

            async with session_factory() as session:
                tenant_id = await session.scalar(select(Trace.tenant_id).where(Trace.session_id == session_id))

            assert tenant_id == "tenant-a"
        finally:
            await _cleanup(session_factory, session_id)
    finally:
        await engine.dispose()