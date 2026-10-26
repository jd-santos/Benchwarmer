"""Task versions: a reviewed bundle prepared as a test, version 1.

A task version takes one evidence bundle and says how a candidate configuration
would be tested on the work it covers. The **cut point** names the last event
the candidate may see; everything after it on the same path, and everything
cited from other conversations, is judge-only evidence. **Criteria** describe
acceptable behavior, each with a method and a rubric version, never the
historical answer's wording. The **reconstruction** level records how much of
the original situation a run can establish, with its gaps. A task version is
``approved`` only after a **leakage review** records who checked that the
candidate section reveals nothing from after the cut point.

This module validates shape only. Resolution against the bundle and its
conversations, the candidate/judge split, and the leakage flags live in
``benchwarmer.services.task_versions``. The exported case record lives in
``benchwarmer.services.case_export``.
"""

from __future__ import annotations

import datetime as dt
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from benchwarmer.evidence import ObjectiveType

TASK_SCHEMA_VERSION = 1
MAX_CRITERIA = 50
MAX_GAPS = 50
MAX_PATHS = 100

TaskKind = Literal["chat", "agent", "coding"]
TASK_KINDS: tuple[TaskKind, ...] = ("chat", "agent", "coding")
TaskStatus = Literal["draft", "approved", "retired"]
TASK_STATUSES: tuple[TaskStatus, ...] = ("draft", "approved", "retired")
CriterionMethod = Literal["deterministic", "llm_judge", "human"]
CRITERION_METHODS: tuple[CriterionMethod, ...] = ("deterministic", "llm_judge", "human")
# The judge-section fields a criterion may read. A deterministic check reads none.
JudgeEvidence = Literal["judge.historical", "judge.feedback", "judge.reviewer_notes"]
ReconstructionLevel = Literal["prompt_only", "fixture_backed", "fixed_multi_turn"]
RECONSTRUCTION_LEVELS: tuple[ReconstructionLevel, ...] = (
    "prompt_only",
    "fixture_backed",
    "fixed_multi_turn",
)
# Assigned per source family, never per task; see docs/experiments.md.
Partition = Literal["development", "calibration", "holdout"]
PARTITIONS: tuple[Partition, ...] = ("development", "calibration", "holdout")
# The reviewer's own verdict on a human-method criterion against the historical
# answer; it becomes the calibration label when a model judge is tried later.
ReviewerLabel = Literal["pass", "fail", "unsure"]

_Identifier = Annotated[str, StringConstraints(min_length=1, max_length=255)]
_Slug = Annotated[
    str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9-]{0,62}$", max_length=63)
]
_Note = Annotated[str, StringConstraints(strip_whitespace=True, max_length=4000)]
_Statement = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)
]
_PathPattern = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=512)
]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class CutPoint(_Strict):
    """The last event the candidate sees, on the bundle's path in one conversation."""

    conversation_id: _Identifier
    revision: _Identifier
    event_id: _Identifier


class Criterion(_Strict):
    """One statement of acceptable behavior and how it is checked."""

    id: _Slug
    statement: _Statement
    method: CriterionMethod
    # Bumped whenever the statement or its checking changes meaning.
    rubric_version: Annotated[int, Field(ge=1)] = 1
    judge_evidence: Annotated[list[JudgeEvidence], Field(max_length=3)] = []
    reviewer_label: ReviewerLabel | None = None
    note: _Note | None = None

    @model_validator(mode="after")
    def _method_rules(self) -> Self:
        if self.method == "deterministic" and self.judge_evidence:
            raise ValueError("a deterministic criterion reads no judge evidence")
        if self.method != "human" and self.reviewer_label is not None:
            raise ValueError("only a human criterion carries a reviewer label")
        if len(set(self.judge_evidence)) != len(self.judge_evidence):
            raise ValueError("judge_evidence lists a field twice")
        return self


class Reconstruction(_Strict):
    """How much of the original situation a run can establish, and what is missing."""

    level: ReconstructionLevel
    gaps: Annotated[list[_Note], Field(max_length=MAX_GAPS)] = []


class ExpectedScope(_Strict):
    """For coding tasks: where changes are expected, gated, or out of bounds."""

    in_scope_paths: Annotated[list[_PathPattern], Field(max_length=MAX_PATHS)] = []
    approval_paths: Annotated[list[_PathPattern], Field(max_length=MAX_PATHS)] = []
    excluded_paths: Annotated[list[_PathPattern], Field(max_length=MAX_PATHS)] = []


class LeakageReview(_Strict):
    """Who checked the candidate section for answer leakage, and which flags they accepted.

    ``accepted_flags`` lists the ids of automatic flags the reviewer looked at
    and judged not to be leaks. Approval requires every current flag to be
    listed here; a flag that appears after the review blocks approval again.
    """

    by: _Identifier
    # Lenient so a JSON timestamp string is accepted under the strict config.
    at: Annotated[dt.datetime, Field(strict=False)]
    accepted_flags: Annotated[list[_Identifier], Field(max_length=200)] = []
    notes: _Note | None = None


class TaskDocument(_Strict):
    """The reviewable content of one task version."""

    schema_version: Literal[1] = TASK_SCHEMA_VERSION
    # The bundle revision this task was prepared from. Items, rationale, and
    # missing evidence stay on the bundle; the task adds the test.
    bundle_id: _Identifier
    bundle_revision: Annotated[int, Field(ge=1)]
    kind: TaskKind
    # Copied from the bundle when drafted; a reviewer may sharpen them here.
    summary: _Note = ""
    objective: _Note = ""
    objective_type: ObjectiveType = "unknown"
    # Shared by every task from the same source conversation, its branches,
    # continuations, and near-duplicates. Partitions are assigned by family.
    family: _Identifier
    cut_point: CutPoint
    reconstruction: Reconstruction
    criteria: Annotated[list[Criterion], Field(max_length=MAX_CRITERIA)] = []
    expected_scope: ExpectedScope | None = None
    leakage_review: LeakageReview | None = None
    partition: Partition | None = None
    status: TaskStatus = "draft"
    reviewer_notes: _Note = ""

    @model_validator(mode="after")
    def _coherent(self) -> Self:
        ids = [criterion.id for criterion in self.criteria]
        if len(set(ids)) != len(ids):
            raise ValueError("criterion ids must be unique within a task")
        if self.expected_scope is not None and self.kind != "coding":
            raise ValueError("expected_scope applies to coding tasks only")
        if self.status == "approved":
            if not self.criteria:
                raise ValueError("an approved task needs at least one criterion")
            if not self.objective:
                raise ValueError("an approved task needs an objective")
            if self.leakage_review is None:
                raise ValueError("an approved task needs a leakage review")
        return self
