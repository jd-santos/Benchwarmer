"""Add tasks and their immutable versions.

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-26
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create task identities and numbered version documents."""
    op.create_table(
        "tasks",
        sa.Column("id", sa.String(length=255), nullable=False),
        sa.Column("bundle_id", sa.String(length=255), nullable=False),
        sa.Column("latest_version", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("length(trim(id)) > 0", name="ck_tasks_id_nonblank"),
        sa.CheckConstraint("latest_version >= 1", name="ck_tasks_latest_positive"),
        sa.ForeignKeyConstraint(
            ["bundle_id"],
            ["evidence_bundles.id"],
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tasks_bundle_id", "tasks", ["bundle_id"])
    op.create_table(
        "task_versions",
        sa.Column("task_id", sa.String(length=255), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("document", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("family", sa.String(length=255), nullable=False),
        sa.Column("producer", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("number >= 1", name="ck_task_versions_number"),
        sa.CheckConstraint(
            "status IN ('draft', 'approved', 'retired')",
            name="ck_task_versions_status",
        ),
        sa.ForeignKeyConstraint(
            ["task_id"], ["tasks.id"], ondelete="RESTRICT", onupdate="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("task_id", "number"),
    )
    op.create_index("ix_task_versions_status", "task_versions", ["status"])
    op.create_index("ix_task_versions_family", "task_versions", ["family"])


def downgrade() -> None:
    """Drop task versions before their identities."""
    op.drop_index("ix_task_versions_family", table_name="task_versions")
    op.drop_index("ix_task_versions_status", table_name="task_versions")
    op.drop_table("task_versions")
    op.drop_index("ix_tasks_bundle_id", table_name="tasks")
    op.drop_table("tasks")
