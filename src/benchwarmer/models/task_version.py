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
    )

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    bundle_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("evidence_bundles.id", ondelete="RESTRICT", onupdate="RESTRICT"),
        nullable=False,
        index=True,
    )
    latest_version: Mapped[int] = mapped_column(Integer(), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=utc_now,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utc_now
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
