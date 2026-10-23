"""Record hand-run harness workflows with their estimated model usage.

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-22
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the harness run table."""
    op.create_table(
        "harness_runs",
        sa.Column("run_id", sa.String(length=255), primary_key=True),
        sa.Column("workflow", sa.String(length=255), nullable=False),
        sa.Column("harness_version", sa.String(length=255), nullable=False),
        sa.Column("provider", sa.String(length=255), nullable=False),
        sa.Column("model", sa.String(length=255), nullable=False),
        sa.Column("thinking_level", sa.String(length=255), nullable=True),
        sa.Column("base_url_override", sa.String(length=1024), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("input_count", sa.Integer(), nullable=False),
        sa.Column("bundle_count", sa.Integer(), nullable=False),
        sa.Column("total_tokens", sa.Integer(), nullable=False),
        sa.Column("estimated_cost", sa.Float(), nullable=False),
        sa.Column("pricing_source", sa.String(length=4000), nullable=False),
        sa.Column("record", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "length(trim(run_id)) > 0", name="ck_harness_runs_id_nonblank"
        ),
        sa.CheckConstraint("input_count >= 0", name="ck_harness_runs_inputs"),
        sa.CheckConstraint("bundle_count >= 0", name="ck_harness_runs_bundles"),
        sa.CheckConstraint("total_tokens >= 0", name="ck_harness_runs_tokens"),
    )
    op.create_index("ix_harness_runs_workflow", "harness_runs", ["workflow"])


def downgrade() -> None:
    """Drop the harness run table."""
    op.drop_index("ix_harness_runs_workflow", table_name="harness_runs")
    op.drop_table("harness_runs")
