"""Versioned evidence references and bundle documents, version 2.

A reference pins one conversation revision, one event, and optionally one
content block and a text range within it. Text ranges count Unicode code points
and are half-open: ``text[start:end]`` in Python selects the referenced text.

A bundle states three things about the work it covers. The ``summary`` is a
sentence or two for a person scanning a list: what the bundle represents. The
``objective`` names the kind of work in general terms ("diagnose duplicate
records from a scheduled batch job"), so bundles can later be grouped by
objective into categories of work. The ``goal`` is what this particular piece
of work tried to achieve, kept as metadata ("find why the nightly
reconciliation posted duplicate credits to 14 accounts"). Version 1 had only
``objective`` and used it for the specific aim; version 1 documents are
upgraded on read.

This module validates shape only. Resolution against stored conversations
lives in ``benchwarmer.services.evidence_bundles``.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

BUNDLE_SCHEMA_VERSION = 3
MAX_BUNDLE_ITEMS = 200

EvidenceRole = Literal["requirement", "action", "result", "correction", "context"]

# The closed vocabulary of work types bundles are grouped by. The free-text
# objective stays alongside it as the finer description. ``unknown`` is a
# legitimate value, not a failure.
ObjectiveType = Literal[
    "bug",
    "feature",
    "refactor",
    "test",
    "performance",
    "infrastructure",
    "analytics",
    "research",
    "design",
    "writing",
    "review",
    "unknown",
]
OBJECTIVE_TYPES: tuple[ObjectiveType, ...] = (
    "bug",
    "feature",
    "refactor",
    "test",
    "performance",
    "infrastructure",
    "analytics",
    "research",
    "design",
    "writing",
    "review",
    "unknown",
)
BundleStatus = Literal["draft", "reviewed", "analysis_only", "rejected"]
BundleOrigin = Literal["human", "generated"]

_Identifier = Annotated[str, StringConstraints(min_length=1, max_length=255)]
_Note = Annotated[str, StringConstraints(strip_whitespace=True, max_length=4000)]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class EvidenceRef(_Strict):
    """A precise, revision-pinned link to captured conversation evidence."""

    conversation_id: _Identifier
    revision: _Identifier
    event_id: _Identifier
    block_id: _Identifier | None = None
    text_start: Annotated[int, Field(ge=0)] | None = None
    text_end: Annotated[int, Field(ge=0)] | None = None

    @model_validator(mode="after")
    def _range(self) -> Self:
        has_start = self.text_start is not None
        if has_start != (self.text_end is not None):
            raise ValueError("text_start and text_end must be given together")
        if has_start and self.block_id is None:
            raise ValueError("a text range requires block_id")
        if has_start and self.text_start >= self.text_end:  # type: ignore[operator]
            raise ValueError("text_end must be greater than text_start")
        return self


class RunProvenance(_Strict):
    """Which harness run and model produced a generated revision.

    Usage is not recorded here because it is only known after the run; the
    run report named by ``report_path`` holds raw usage and the pricing source.
    """

    run_id: _Identifier
    workflow: _Identifier
    harness_version: _Identifier
    provider: _Identifier
    model: _Identifier
    thinking_level: _Identifier | None = None
    report_path: (
        Annotated[str, StringConstraints(min_length=1, max_length=1024)] | None
    ) = None


class BundleItem(_Strict):
    """One piece of evidence and why it matters to the bundle objective."""

    ref: EvidenceRef
    role: EvidenceRole
    note: _Note | None = None


class BundleDocument(_Strict):
    """The reviewable content of one bundle revision."""

    schema_version: Literal[3] = BUNDLE_SCHEMA_VERSION
    # What the bundle represents, in a sentence or two for a human reader.
    summary: _Note = ""
    # The kind of work, in general terms; the axis bundles are grouped on.
    objective: _Note = ""
    # The closed category of that work; the first grouping level above the objective.
    objective_type: ObjectiveType = "unknown"
    # What this particular piece of work tried to achieve.
    goal: _Note = ""
    status: BundleStatus = "draft"
    items: Annotated[list[BundleItem], Field(min_length=1, max_length=MAX_BUNDLE_ITEMS)]
    rationale: _Note | None = None
    missing_evidence: Annotated[list[_Note], Field(max_length=50)] = []

    @model_validator(mode="before")
    @classmethod
    def _upgrade_earlier_versions(cls, data: Any) -> Any:
        """Read version 1 and 2 documents as version 3.

        Version 1 kept the specific aim in ``objective``, so it becomes the
        ``goal``. The text also stays in ``objective`` until a reviewer writes
        the general kind of work, so a reviewed bundle stays valid. Version 2
        had no ``objective_type``; it reads as ``unknown`` until classified.
        """
        if isinstance(data, dict) and data.get("schema_version") in (1, 2):
            upgraded = dict(data)
            if upgraded["schema_version"] == 1:
                upgraded.setdefault("goal", upgraded.get("objective", ""))
            upgraded["schema_version"] = BUNDLE_SCHEMA_VERSION
            upgraded.setdefault("objective_type", "unknown")
            return upgraded
        return data

    @model_validator(mode="after")
    def _reviewable(self) -> Self:
        if self.status not in ("draft", "rejected") and not self.objective:
            raise ValueError("a reviewed or analysis-only bundle needs an objective")
        if self.status == "rejected" and not self.rationale:
            raise ValueError("a rejected bundle needs a rationale saying why")
        seen: set[EvidenceRef] = set()
        for item in self.items:
            if item.ref in seen:
                raise ValueError("a bundle cannot cite the same evidence twice")
            seen.add(item.ref)
        return self
