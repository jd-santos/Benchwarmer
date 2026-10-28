"""Assign development, calibration, and holdout partitions by source family.

A family is every task from the same source conversation, its branches and
continuations, and the bundles derived from them (``TaskDocument.family``).
Partitions are decided per family, never per task, so no family can straddle
the divide between what guides changes and what measures them. The decision
is a deterministic hash of the family key and a seed: the same seed and family
always land on the same side, whatever else is in scope, so a later run with
the same seed adds new families without moving old ones. Every run is
recorded with its seed, split, scope, time, and resulting counts.

Nothing here starts model work.
"""

from __future__ import annotations

from dataclasses import dataclass
import datetime as dt
import hashlib
import math
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from benchwarmer.models.source import utc_now
from benchwarmer.models.task_version import Task, TaskPartitionAssignment, TaskVersion
from benchwarmer.tasks import PARTITIONS, Partition

# Development gets the larger share: it guides task construction, prompts and
# harness changes. Calibration tunes rubrics and judges; holdout is read once.
DEFAULT_SPLIT: dict[Partition, float] = {
    "development": 0.6,
    "calibration": 0.2,
    "holdout": 0.2,
}
# Retired tasks keep whatever partition they had; they are never run again.
DEFAULT_SCOPE_STATUSES: tuple[str, ...] = ("draft", "approved")
_SPLIT_TOLERANCE = 1e-9
_HASH_BITS = 64


class PartitionSplitInvalid(ValueError):
    """Raised when the fractions are negative or do not sum to one."""


@dataclass(frozen=True)
class PartitionAssignment:
    """One recorded run of partition assignment."""

    id: str
    seed: str
    split: dict[str, float]
    scope: dict[str, list[str]]
    families: dict[str, str]
    task_counts: dict[str, int]
    family_counts: dict[str, int]
    task_count: int
    family_count: int
    # Families whose partition differs from the previous assignment they had.
    moved_families: int
    producer: str
    created_at: dt.datetime


def validate_split(split: dict[str, float]) -> dict[Partition, float]:
    """Return the split in partition order, or raise when it is not a split."""
    if set(split) != set(PARTITIONS):
        raise PartitionSplitInvalid(
            "The split must name development, calibration, and holdout once each."
        )
    if any(value < 0 for value in split.values()):
        raise PartitionSplitInvalid("Split fractions cannot be negative.")
    if not math.isclose(sum(split.values()), 1.0, abs_tol=_SPLIT_TOLERANCE):
        raise PartitionSplitInvalid("Split fractions must sum to 1.")
    return {partition: float(split[partition]) for partition in PARTITIONS}


def family_point(seed: str, family: str) -> float:
    """A stable position in [0, 1) for one family under one seed."""
    digest = hashlib.sha256(f"{seed}\n{family}".encode()).digest()
    return int.from_bytes(digest[:8], "big") / 2**_HASH_BITS


def partition_for(seed: str, family: str, split: dict[Partition, float]) -> Partition:
    """Place one family: the hash point falls into the cumulative split."""
    point = family_point(seed, family)
    edge = 0.0
    for partition in PARTITIONS:
        edge += split[partition]
        if point < edge:
            return partition
    # Rounding left the last edge just short of 1.
    return PARTITIONS[-1]


def assign_partitions(
    session: Session,
    *,
    seed: str,
    split: dict[str, float] | None = None,
    statuses: tuple[str, ...] | list[str] = DEFAULT_SCOPE_STATUSES,
    producer: str = "web",
) -> PartitionAssignment:
    """Assign every in-scope task's partition by family and record the run.

    The scope is the set of tasks whose latest version has one of ``statuses``.
    Each task's ``partition`` is set from its family's hash, replacing any
    earlier assignment; the version documents are not touched.
    """
    checked = validate_split(dict(DEFAULT_SPLIT) if split is None else split)
    scope_statuses = tuple(dict.fromkeys(statuses))
    if not scope_statuses:
        raise PartitionSplitInvalid("The scope must name at least one status.")
    rows = list(
        session.execute(
            select(Task, TaskVersion)
            .join(
                TaskVersion,
                (TaskVersion.task_id == Task.id)
                & (TaskVersion.number == Task.latest_version),
            )
            .where(TaskVersion.status.in_(scope_statuses))
            .order_by(Task.id)
        )
    )
    families: dict[str, Partition] = {}
    for _, version in rows:
        if version.family not in families:
            families[version.family] = partition_for(seed, version.family, checked)

    task_counts: dict[str, int] = {partition: 0 for partition in PARTITIONS}
    family_counts: dict[str, int] = {partition: 0 for partition in PARTITIONS}
    for partition in families.values():
        family_counts[partition] += 1
    moved = 0
    assignment_id = f"partition-{uuid.uuid4().hex}"
    now = utc_now()
    seen_moved: set[str] = set()
    for task, version in rows:
        partition = families[version.family]
        if (
            task.partition_assignment_id is not None
            and task.partition != partition
            and version.family not in seen_moved
        ):
            seen_moved.add(version.family)
            moved += 1
        task_counts[partition] += 1

    # The run is recorded before any task points at it; foreign keys are on.
    record = TaskPartitionAssignment(
        id=assignment_id,
        seed=seed,
        split=dict(checked),
        scope={"statuses": list(scope_statuses)},
        families=dict(sorted(families.items())),
        counts={"tasks": task_counts, "families": family_counts},
        task_count=len(rows),
        family_count=len(families),
        producer=producer,
        created_at=now,
    )
    session.add(record)
    session.flush()
    for task, version in rows:
        task.partition = families[version.family]
        task.partition_assignment_id = assignment_id
    session.commit()
    return PartitionAssignment(
        id=record.id,
        seed=seed,
        split=dict(checked),
        scope={"statuses": list(scope_statuses)},
        families=dict(sorted(families.items())),
        task_counts=task_counts,
        family_counts=family_counts,
        task_count=len(rows),
        family_count=len(families),
        moved_families=moved,
        producer=producer,
        created_at=now,
    )


def latest_assignment(session: Session) -> PartitionAssignment | None:
    """The most recent recorded run, if any."""
    row = session.execute(
        select(TaskPartitionAssignment)
        .order_by(TaskPartitionAssignment.created_at.desc(), TaskPartitionAssignment.id)
        .limit(1)
    ).scalar_one_or_none()
    if row is None:
        return None
    return PartitionAssignment(
        id=row.id,
        seed=row.seed,
        split=dict(row.split),
        scope={"statuses": list(row.scope.get("statuses", []))},
        families=dict(row.families),
        task_counts=dict(row.counts["tasks"]),
        family_counts=dict(row.counts["families"]),
        task_count=row.task_count,
        family_count=row.family_count,
        moved_families=0,
        producer=row.producer,
        created_at=row.created_at,
    )


__all__ = [
    "DEFAULT_SCOPE_STATUSES",
    "DEFAULT_SPLIT",
    "PartitionAssignment",
    "PartitionSplitInvalid",
    "assign_partitions",
    "family_point",
    "latest_assignment",
    "partition_for",
    "validate_split",
]
