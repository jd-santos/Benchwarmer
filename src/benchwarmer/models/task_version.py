"""Tasks and their immutable, numbered versions."""

from __future__ import annotations

import datetime as dt
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    ForeignKey,
    Integer,
    PrimaryKeyConstraint,
    String,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from benchwarmer.models.base import Base
from benchwarmer.models.source import UTCDateTime, utc_now


class Task(Base):
    """A task identity; its content lives in numbered versions."""

    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint("length(trim(id)) > 0", name="ck_tasks_id_nonblank"),
        CheckConstraint("latest_version >= 1", name="ck_tasks_latest_positive"),
        CheckConstraint(
            "partition IS NULL OR partition IN "
            "('development', 'calibration', 'holdout')",
            name="ck_tasks_partition",
        ),
    )

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    bundle_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("evidence_bundles.id", ondelete="RESTRICT", onupdate="RESTRICT"),
        nullable=False,
        index=True,
    )
    latest_version: Mapped[int] = mapped_column(Integer(), nullable=False)
    # Assigned by family across tasks, never edited per version; see
    # ``benchwarmer.services.task_partitions``. Null until the first assignment.
    partition: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    partition_assignment_id: Mapped[str | None] = mapped_column(
        String(255),
        ForeignKey(
            "task_partition_assignments.id", ondelete="RESTRICT", onupdate="RESTRICT"
        ),
        nullable=True,
    )
    created_at: Mapped[dt.datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=utc_now,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utc_now
    )


class TaskPartitionAssignment(Base):
    """One run of partition assignment by family: its inputs and what it produced."""

    __tablename__ = "task_partition_assignments"
    __table_args__ = (
        CheckConstraint(
            "length(trim(id)) > 0", name="ck_task_partition_assignments_id_nonblank"
        ),
        CheckConstraint(
            "length(trim(seed)) > 0", name="ck_task_partition_assignments_seed"
        ),
        CheckConstraint(
            "task_count >= 0", name="ck_task_partition_assignments_task_count"
        ),
        CheckConstraint(
            "family_count >= 0", name="ck_task_partition_assignments_family_count"
        ),
    )

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    seed: Mapped[str] = mapped_column(String(255), nullable=False)
    split: Mapped[dict[str, Any]] = mapped_column(JSON(), nullable=False)
    scope: Mapped[dict[str, Any]] = mapped_column(JSON(), nullable=False)
    # family -> partition, so one run can be compared with the next.
    families: Mapped[dict[str, Any]] = mapped_column(JSON(), nullable=False)
    counts: Mapped[dict[str, Any]] = mapped_column(JSON(), nullable=False)
    task_count: Mapped[int] = mapped_column(Integer(), nullable=False)
    family_count: Mapped[int] = mapped_column(Integer(), nullable=False)
    producer: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utc_now, index=True
    )


class TaskVersion(Base):
    """One immutable, validated task document; status is mirrored for queries."""

    __tablename__ = "task_versions"
    __table_args__ = (
        PrimaryKeyConstraint("task_id", "number"),
        CheckConstraint("number >= 1", name="ck_task_versions_number"),
        CheckConstraint(
            "status IN ('draft', 'approved', 'retired')",
            name="ck_task_versions_status",
        ),
    )

    task_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("tasks.id", ondelete="RESTRICT", onupdate="RESTRICT"),
        nullable=False,
    )
    number: Mapped[int] = mapped_column(Integer(), nullable=False)
    document: Mapped[dict[str, Any]] = mapped_column(JSON(), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    family: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    producer: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utc_now
    )
