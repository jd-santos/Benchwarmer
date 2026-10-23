"""Store and read records of hand-run harness workflows."""

from __future__ import annotations

from dataclasses import dataclass
import datetime as dt

from sqlalchemy import select
from sqlalchemy.orm import Session

from benchwarmer.models.harness_run import HarnessRun
from benchwarmer.models.source import utc_now
from benchwarmer.runs import HarnessRunRecord, parse_timestamp


class RunNotFound(LookupError):
    """Raised when no run with the requested id was recorded."""


@dataclass(frozen=True)
class RunSummary:
    run_id: str
    workflow: str
    provider: str
    model: str
    thinking_level: str | None
    base_url_override: str | None
    started_at: dt.datetime
    finished_at: dt.datetime
    input_count: int
    bundle_count: int
    total_tokens: int
    estimated_cost: float
    pricing_source: str


def record_run(session: Session, record: HarnessRunRecord) -> HarnessRunRecord:
    """Store a run record, replacing an earlier record of the same run.

    A workflow may send its record more than once (a retry, or a resumed run
    that finished later), so the latest record wins.
    """
    row = session.get(HarnessRun, record.run_id)
    now = utc_now()
    if row is None:
        row = HarnessRun(run_id=record.run_id, created_at=now)
        session.add(row)
    row.workflow = record.workflow
    row.harness_version = record.harness_version
    row.provider = record.model.provider
    row.model = record.model.model_id
    row.thinking_level = record.model.thinking_level
    row.base_url_override = record.model.base_url_override
    row.started_at = parse_timestamp(record.started_at)
    row.finished_at = parse_timestamp(record.finished_at)
    row.input_count = len(record.inputs)
    row.bundle_count = record.bundle_count
    row.total_tokens = record.usage_total.total_tokens
    row.estimated_cost = record.usage_total.estimated_cost
    row.pricing_source = record.pricing_source
    row.record = record.model_dump(mode="json")
    row.updated_at = now
    session.commit()
    return record


def get_run(session: Session, run_id: str) -> HarnessRunRecord:
    """Return the full record of one run."""
    row = session.get(HarnessRun, run_id)
    if row is None:
        raise RunNotFound(run_id)
    return HarnessRunRecord.model_validate(row.record)


def list_runs(
    session: Session, *, workflow: str | None = None
) -> tuple[RunSummary, ...]:
    """List recorded runs, most recently started first."""
    query = select(HarnessRun).order_by(HarnessRun.started_at.desc(), HarnessRun.run_id)
    if workflow is not None:
        query = query.where(HarnessRun.workflow == workflow)
    return tuple(
        RunSummary(
            run_id=row.run_id,
            workflow=row.workflow,
            provider=row.provider,
            model=row.model,
            thinking_level=row.thinking_level,
            base_url_override=row.base_url_override,
            started_at=row.started_at,
            finished_at=row.finished_at,
            input_count=row.input_count,
            bundle_count=row.bundle_count,
            total_tokens=row.total_tokens,
            estimated_cost=row.estimated_cost,
            pricing_source=row.pricing_source,
        )
        for row in session.execute(query).scalars()
    )
