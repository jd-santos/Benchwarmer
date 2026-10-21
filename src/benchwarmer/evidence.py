"""Versioned evidence references and bundle documents, version 1.

A reference pins one conversation revision, one event, and optionally one
content block and a text range within it. Text ranges count Unicode code points
and are half-open: ``text[start:end]`` in Python selects the referenced text.

This module validates shape only. Resolution against stored conversations
lives in ``benchwarmer.services.evidence_bundles``.
"""

from __future__ import annotations

from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

BUNDLE_SCHEMA_VERSION = 1
MAX_BUNDLE_ITEMS = 200

EvidenceRole = Literal["requirement", "action", "result", "correction", "context"]
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


class BundleItem(_Strict):
    """One piece of evidence and why it matters to the bundle objective."""

    ref: EvidenceRef
    role: EvidenceRole
    note: _Note | None = None


class BundleDocument(_Strict):
    """The reviewable content of one bundle revision."""

    schema_version: Literal[1] = BUNDLE_SCHEMA_VERSION
    objective: _Note = ""
    status: BundleStatus = "draft"
    items: Annotated[list[BundleItem], Field(min_length=1, max_length=MAX_BUNDLE_ITEMS)]
    rationale: _Note | None = None
    missing_evidence: Annotated[list[_Note], Field(max_length=50)] = []

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
