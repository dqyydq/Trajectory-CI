from __future__ import annotations

import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class SpanType(str, enum.Enum):
    llm_call = "llm_call"


class SpanStatus(str, enum.Enum):
    in_progress = "in_progress"
    success = "success"
    error = "error"


class Trace(Base):
    __tablename__ = "traces"

    trace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    trace_metadata: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict, server_default="{}")

    spans: Mapped[list["Span"]] = relationship(
        back_populates="trace",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class Span(Base):
    __tablename__ = "spans"

    span_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("traces.trace_id", ondelete="CASCADE"),
        nullable=False,
    )
    parent_span_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("spans.span_id", ondelete="SET NULL"),
        nullable=True,
    )
    span_type: Mapped[SpanType] = mapped_column(Enum(SpanType, name="span_type"), nullable=False)
    model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    request_body: Mapped[dict | list | None] = mapped_column(JSONB, nullable=True)
    response_body: Mapped[dict | list | None] = mapped_column(JSONB, nullable=True)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[SpanStatus] = mapped_column(Enum(SpanStatus, name="span_status"), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_stream: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    trace: Mapped[Trace] = relationship(back_populates="spans")
    parent_span: Mapped["Span | None"] = relationship(remote_side=[span_id], back_populates="child_spans")
    child_spans: Mapped[list["Span"]] = relationship(back_populates="parent_span")


Index(
    "uq_traces_session_id_not_null",
    Trace.session_id,
    unique=True,
    postgresql_where=Trace.session_id.is_not(None),
)
Index("ix_traces_session_started_at", Trace.session_id, Trace.started_at)
Index("ix_spans_trace_started_at", Span.trace_id, Span.started_at)
Index("ix_spans_parent_span_id", Span.parent_span_id)
Index("ix_spans_model_status", Span.model, Span.status)
Index("ix_spans_started_at", Span.started_at)

