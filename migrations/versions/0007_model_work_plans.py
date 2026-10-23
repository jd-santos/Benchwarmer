"""Store frozen, approved plans for model work the application starts.

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-23
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the model work plan table."""
    op.create_table(
        "model_work_plans",
        sa.Column("id", sa.String(length=255), primary_key=True),
        sa.Column("workflow", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("digest", sa.String(length=64), nullable=False),
        sa.Column("plan", sa.JSON(), nullable=False),
        sa.Column("run_id", sa.String(length=255), nullable=True),
        sa.Column("pid", sa.Integer(), nullable=True),
        sa.Column("exit_code", sa.Integer(), nullable=True),
        sa.Column("log_path", sa.String(length=1024), nullable=True),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "length(trim(id)) > 0", name="ck_model_work_plans_id_nonblank"
        ),
        sa.CheckConstraint(
            "status IN ('proposed', 'approved', 'running', 'finished', 'failed', "
            "'cancelled', 'interrupted')",
            name="ck_model_work_plans_status",
        ),
    )
    op.create_index("ix_model_work_plans_workflow", "model_work_plans", ["workflow"])
    op.create_index("ix_model_work_plans_status", "model_work_plans", ["status"])


def downgrade() -> None:
    """Drop the model work plan table."""
    op.drop_index("ix_model_work_plans_status", table_name="model_work_plans")
    op.drop_index("ix_model_work_plans_workflow", table_name="model_work_plans")
    op.drop_table("model_work_plans")
