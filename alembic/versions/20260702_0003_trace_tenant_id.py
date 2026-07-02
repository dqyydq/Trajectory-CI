from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260702_0003"
down_revision = "20260702_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "traces",
        sa.Column("tenant_id", sa.String(length=255), server_default="default", nullable=False),
    )
    op.create_index("ix_traces_tenant_started_at", "traces", ["tenant_id", "started_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_traces_tenant_started_at", table_name="traces")
    op.drop_column("traces", "tenant_id")