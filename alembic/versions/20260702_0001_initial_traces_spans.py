from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260702_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    span_type = postgresql.ENUM("llm_call", name="span_type", create_type=False)
    span_status = postgresql.ENUM("in_progress", "success", "error", name="span_status", create_type=False)
    span_type.create(op.get_bind(), checkfirst=True)
    span_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "traces",
        sa.Column("trace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", sa.String(length=255), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.PrimaryKeyConstraint("trace_id"),
    )
    op.create_table(
        "spans",
        sa.Column("span_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("trace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parent_span_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("span_type", span_type, nullable=False),
        sa.Column("model", sa.String(length=255), nullable=True),
        sa.Column("request_body", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("response_body", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("cost_usd", sa.Numeric(12, 6), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("status", span_status, nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("is_stream", sa.Boolean(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["parent_span_id"], ["spans.span_id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["trace_id"], ["traces.trace_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("span_id"),
    )
    op.create_index(
        "uq_traces_session_id_not_null",
        "traces",
        ["session_id"],
        unique=True,
        postgresql_where=sa.text("session_id IS NOT NULL"),
    )
    op.create_index("ix_traces_session_started_at", "traces", ["session_id", "started_at"], unique=False)
    op.create_index("ix_spans_trace_started_at", "spans", ["trace_id", "started_at"], unique=False)
    op.create_index("ix_spans_parent_span_id", "spans", ["parent_span_id"], unique=False)
    op.create_index("ix_spans_model_status", "spans", ["model", "status"], unique=False)
    op.create_index("ix_spans_started_at", "spans", ["started_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_spans_started_at", table_name="spans")
    op.drop_index("ix_spans_model_status", table_name="spans")
    op.drop_index("ix_spans_parent_span_id", table_name="spans")
    op.drop_index("ix_spans_trace_started_at", table_name="spans")
    op.drop_index("ix_traces_session_started_at", table_name="traces")
    op.drop_index("uq_traces_session_id_not_null", table_name="traces")
    op.drop_table("spans")
    op.drop_table("traces")
    postgresql.ENUM(name="span_status").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="span_type").drop(op.get_bind(), checkfirst=True)

