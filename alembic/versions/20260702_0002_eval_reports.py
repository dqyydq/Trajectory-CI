from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260702_0002"
down_revision = "20260702_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE span_type ADD VALUE IF NOT EXISTS 'llm_judge'")
    eval_task_status = postgresql.ENUM(
        "not_run",
        "hard_check_failed",
        "judged",
        "judge_failed",
        name="eval_task_status",
        create_type=False,
    )
    eval_task_status.create(op.get_bind(), checkfirst=True)

    op.add_column("traces", sa.Column("eval_task_id", sa.String(length=255), nullable=True))
    op.add_column("traces", sa.Column("eval_run_id", sa.String(length=255), nullable=True))
    op.create_index("ix_traces_eval_task_run", "traces", ["eval_task_id", "eval_run_id"], unique=False)

    op.create_table(
        "eval_reports",
        sa.Column("report_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_set_name", sa.String(length=255), nullable=False),
        sa.Column("run_id_a", sa.String(length=255), nullable=False),
        sa.Column("run_id_b", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("summary", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.PrimaryKeyConstraint("report_id"),
    )
    op.create_table(
        "eval_task_results",
        sa.Column("result_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("report_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_id", sa.String(length=255), nullable=False),
        sa.Column("run_a_status", eval_task_status, nullable=False),
        sa.Column("run_b_status", eval_task_status, nullable=False),
        sa.Column("run_a_check_passed", sa.Boolean(), nullable=True),
        sa.Column("run_a_judge_score", sa.Numeric(3, 2), nullable=True),
        sa.Column("run_b_check_passed", sa.Boolean(), nullable=True),
        sa.Column("run_b_judge_score", sa.Numeric(3, 2), nullable=True),
        sa.Column("regressed", sa.Boolean(), nullable=False),
        sa.Column("detail", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.ForeignKeyConstraint(["report_id"], ["eval_reports.report_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("result_id"),
    )
    op.create_index("ix_eval_reports_created_at", "eval_reports", ["created_at"], unique=False)
    op.create_index(
        "ix_eval_reports_task_set_runs",
        "eval_reports",
        ["task_set_name", "run_id_a", "run_id_b"],
        unique=False,
    )
    op.create_index(
        "ix_eval_task_results_report_task",
        "eval_task_results",
        ["report_id", "task_id"],
        unique=True,
    )
    op.create_index("ix_eval_task_results_regressed", "eval_task_results", ["regressed"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_eval_task_results_regressed", table_name="eval_task_results")
    op.drop_index("ix_eval_task_results_report_task", table_name="eval_task_results")
    op.drop_index("ix_eval_reports_task_set_runs", table_name="eval_reports")
    op.drop_index("ix_eval_reports_created_at", table_name="eval_reports")
    op.drop_table("eval_task_results")
    op.drop_table("eval_reports")
    op.drop_index("ix_traces_eval_task_run", table_name="traces")
    op.drop_column("traces", "eval_run_id")
    op.drop_column("traces", "eval_task_id")
    postgresql.ENUM(name="eval_task_status").drop(op.get_bind(), checkfirst=True)