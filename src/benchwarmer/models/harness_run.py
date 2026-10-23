"""Records of hand-run harness workflows and their estimated model usage."""

from __future__ import annotations

import datetime as dt
from typing import Any

from sqlalchemy import JSON, CheckConstraint, Float, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from benchwarmer.models.base import Base
from benchwarmer.models.source import UTCDateTime, utc_now


class HarnessRun(Base):
    """One harness run; the full typed record is kept in ``record``."""

    __tablename__ = "harness_runs"
    __table_args__ = (
        CheckConstraint("length(trim(run_id)) > 0", name="ck_harness_runs_id_nonblank"),
        CheckConstraint("input_count >= 0", name="ck_harness_runs_inputs"),
        CheckConstraint("bundle_count >= 0", name="ck_harness_runs_bundles"),
        CheckConstraint("total_tokens >= 0", name="ck_harness_runs_tokens"),
    )

    run_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    workflow: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    harness_version: Mapped[str] = mapped_column(String(255), nullable=False)
    provider: Mapped[str] = mapped_column(String(255), nullable=False)
    model: Mapped[str] = mapped_column(String(255), nullable=False)
    thinking_level: Mapped[str | None] = mapped_column(String(255), nullable=True)
    base_url_override: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    started_at: Mapped[dt.datetime] = mapped_column(UTCDateTime(), nullable=False)
    finished_at: Mapped[dt.datetime] = mapped_column(UTCDateTime(), nullable=False)
    input_count: Mapped[int] = mapped_column(Integer(), nullable=False)
    bundle_count: Mapped[int] = mapped_column(Integer(), nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer(), nullable=False)
    # A catalog estimate in USD, never a provider charge; see ``pricing_source``.
    estimated_cost: Mapped[float] = mapped_column(Float(), nullable=False)
    pricing_source: Mapped[str] = mapped_column(String(4000), nullable=False)
    record: Mapped[dict[str, Any]] = mapped_column(JSON(), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=utc_now,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utc_now
    )
