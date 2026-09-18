"""Read source import status without inventing unavailable evidence."""

from __future__ import annotations

from dataclasses import dataclass
import datetime as dt
from types import MappingProxyType
from typing import Literal, TypeAlias

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from benchwarmer.models.import_batch import ImportBatch
from benchwarmer.models.source import Source

CoverageState: TypeAlias = Literal["available", "partial", "unavailable", "unknown"]

COVERAGE_DIMENSIONS = (
    "sessions",
    "token_usage",
    "request_ids",
    "actual_charges",
    "list_price_estimates",
    "subscription_expense",
    "quota",
    "credits",
    "prompts",
    "classifications",
)


@dataclass(frozen=True)
class SourceStatus:
    """A configured source and the evidence known about its imports."""

    id: str
    kind: str
    display_name: str
    last_successful_import_at: dt.datetime | None
    coverage: dict[str, CoverageState]


def list_source_status(session: Session) -> tuple[SourceStatus, ...]:
    """Return configured sources in stable display order."""
    last_successful_import = (
        select(func.max(ImportBatch.completed_at))
        .where(
            ImportBatch.source_id == Source.id,
            ImportBatch.outcome == "succeeded",
        )
        .correlate(Source)
        .scalar_subquery()
    )
    rows = session.execute(
        select(Source, last_successful_import).order_by(
            func.lower(Source.display_name), Source.id
        )
    ).all()

    statuses: list[SourceStatus] = []
    for source, last_successful_at in rows:
        configured = (
            source.configured_coverage.dimensions
            if source.configured_coverage is not None
            else MappingProxyType({})
        )
        coverage: dict[str, CoverageState] = {
            dimension: configured.get(dimension, "unknown")
            for dimension in COVERAGE_DIMENSIONS
        }
        statuses.append(
            SourceStatus(
                id=source.id,
                kind=source.kind,
                display_name=source.display_name,
                last_successful_import_at=last_successful_at,
                coverage=coverage,
            )
        )
    return tuple(statuses)
