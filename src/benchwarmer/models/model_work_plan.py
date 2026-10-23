"""Frozen, explicitly approved plans for model work the application starts."""

from __future__ import annotations

import datetime as dt
from typing import Any

from sqlalchemy import JSON, CheckConstraint, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from benchwarmer.models.base import Base
from benchwarmer.models.source import UTCDateTime, utc_now

PLAN_STATUSES = (
    "proposed",
    "approved",
    "running",
    "finished",
    "failed",
    "cancelled",
    "interrupted",
)


class ModelWorkPlan(Base):
    """One previewed plan; approval binds to its digest, execution to one process."""

    __tablename__ = "model_work_plans"
    __table_args__ = (
        CheckConstraint("length(trim(id)) > 0", name="ck_model_work_plans_id_nonblank"),
        CheckConstraint(
            "status IN ('proposed', 'approved', 'running', 'finished', 'failed', "
            "'cancelled', 'interrupted')",
            name="ck_model_work_plans_status",
        ),
    )

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    workflow: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    # sha256 of the canonical plan; approval must quote it exactly.
    digest: Mapped[str] = mapped_column(String(64), nullable=False)
    # The frozen plan: inputs with pinned revisions, model, limits, instructions.
    plan: Mapped[dict[str, Any]] = mapped_column(JSON(), nullable=False)
    run_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    pid: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    exit_code: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    log_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    error_summary: Mapped[str | None] = mapped_column(Text(), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=utc_now,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    approved_at: Mapped[dt.datetime | None] = mapped_column(
        UTCDateTime(), nullable=True
    )
    started_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    finished_at: Mapped[dt.datetime | None] = mapped_column(
        UTCDateTime(), nullable=True
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utc_now
    )
