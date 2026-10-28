"""Record family-level partition assignments and the partition on each task.

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-27
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PARTITION_CHECK = (
    "partition IS NULL OR partition IN ('development', 'calibration', 'holdout')"
)


def _tasks_before() -> sa.Table:
    """``tasks`` as 0008 created it, so SQLite batch mode needs no reflection."""
    return sa.Table(
        "tasks",
        sa.MetaData(),
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
        sa.Index("ix_tasks_bundle_id", "bundle_id"),
    )


def _tasks_after() -> sa.Table:
    """``tasks`` as this revision leaves it, for the downgrade's batch copy."""
    table = sa.Table(
        "tasks",
        sa.MetaData(),
        sa.Column("id", sa.String(length=255), nullable=False),
        sa.Column("bundle_id", sa.String(length=255), nullable=False),
        sa.Column("latest_version", sa.Integer(), nullable=False),
        sa.Column("partition", sa.String(length=32), nullable=True),
        sa.Column("partition_assignment_id", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("length(trim(id)) > 0", name="ck_tasks_id_nonblank"),
        sa.CheckConstraint("latest_version >= 1", name="ck_tasks_latest_positive"),
        sa.CheckConstraint(_PARTITION_CHECK, name="ck_tasks_partition"),
        sa.ForeignKeyConstraint(
            ["bundle_id"],
            ["evidence_bundles.id"],
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["partition_assignment_id"],
            ["task_partition_assignments.id"],
            name="fk_tasks_partition_assignment_id",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.Index("ix_tasks_bundle_id", "bundle_id"),
        sa.Index("ix_tasks_partition", "partition"),
    )
    return table


def upgrade() -> None:
    """Create the assignment log and move the partition to task-level metadata."""
    op.create_table(
        "task_partition_assignments",
        sa.Column("id", sa.String(length=255), nullable=False),
        sa.Column("seed", sa.String(length=255), nullable=False),
        # {"development": 0.6, "calibration": 0.2, "holdout": 0.2}
        sa.Column("split", sa.JSON(), nullable=False),
        # {"statuses": [...]}: which tasks were considered.
        sa.Column("scope", sa.JSON(), nullable=False),
        # family -> partition, for comparing one run with the next.
        sa.Column("families", sa.JSON(), nullable=False),
        # {"tasks": {partition: n}, "families": {partition: n}}
        sa.Column("counts", sa.JSON(), nullable=False),
        sa.Column("task_count", sa.Integer(), nullable=False),
        sa.Column("family_count", sa.Integer(), nullable=False),
        sa.Column("producer", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "length(trim(id)) > 0", name="ck_task_partition_assignments_id_nonblank"
        ),
        sa.CheckConstraint(
            "length(trim(seed)) > 0", name="ck_task_partition_assignments_seed"
        ),
        sa.CheckConstraint(
            "task_count >= 0", name="ck_task_partition_assignments_task_count"
        ),
        sa.CheckConstraint(
            "family_count >= 0", name="ck_task_partition_assignments_family_count"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_task_partition_assignments_created_at",
        "task_partition_assignments",
        ["created_at"],
    )
    with op.batch_alter_table(
        "tasks", copy_from=_tasks_before(), recreate="always"
    ) as batch:
        batch.add_column(sa.Column("partition", sa.String(length=32), nullable=True))
        batch.add_column(
            sa.Column("partition_assignment_id", sa.String(length=255), nullable=True)
        )
        batch.create_check_constraint("ck_tasks_partition", _PARTITION_CHECK)
        batch.create_foreign_key(
            "fk_tasks_partition_assignment_id",
            "task_partition_assignments",
            ["partition_assignment_id"],
            ["id"],
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        )
        batch.create_index("ix_tasks_partition", ["partition"])


def downgrade() -> None:
    """Drop the task-level partition before the assignment log it points at."""
    with op.batch_alter_table(
        "tasks", copy_from=_tasks_after(), recreate="always"
    ) as batch:
        batch.drop_index("ix_tasks_partition")
        batch.drop_constraint("fk_tasks_partition_assignment_id", type_="foreignkey")
        batch.drop_constraint("ck_tasks_partition", type_="check")
        batch.drop_column("partition_assignment_id")
        batch.drop_column("partition")
    op.drop_index(
        "ix_task_partition_assignments_created_at",
        table_name="task_partition_assignments",
    )
    op.drop_table("task_partition_assignments")
