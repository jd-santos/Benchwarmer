"""Export an approved task version as a case record.

A case record is one JSON document with two sections that are stored together
and meant to be served apart: ``candidate`` is what a configuration under test
receives, ``judge`` is the historical evidence reserved for grading it. The
export is deterministic for a given task version and term list, so repeating
it yields the same bytes and the same digest. Both sections pass through the
deterministic scrubber with one placeholder table, and the redaction manifest
records counts by kind, never the original values.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from benchwarmer.anonymize import (
    ANONYMIZE_PRODUCER,
    ANONYMIZE_PRODUCER_VERSION,
    Scrubber,
)
from benchwarmer.evidence import EvidenceRef
from benchwarmer.services.evidence_bundles import LoadedConversation, load_conversations
from benchwarmer.services.task_versions import (
    TaskDetail,
    TaskInvalid,
    TaskIssue,
    get_task,
)

CASE_SCHEMA_VERSION = 1
SCRUB_VERSION = f"{ANONYMIZE_PRODUCER}-{ANONYMIZE_PRODUCER_VERSION}"
# Reasoning is the historical model's private trace; a candidate never sees it.
_CANDIDATE_OMITTED = ("reasoning",)


class CaseExportNotApproved(RuntimeError):
    """Raised when the requested task version is not approved."""

    def __init__(self, status: str) -> None:
        super().__init__(f"task version is {status}, not approved")
        self.status = status


class CaseRecord(BaseModel):
    """The exported document; see the module docstring for the two sections."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    schema_version: Literal[1] = CASE_SCHEMA_VERSION
    case: dict[str, Any]
    candidate: dict[str, Any]
    judge: dict[str, Any]
    # sha256 over the canonical JSON of the three sections above.
    digest: str


def _block(part: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": part["kind"],
        "text": part["text"] if isinstance(part["text"], str) else None,
        "tool_call_id": part.get("tool_call_id"),
    }


def _message(event: dict[str, Any], *, omit: tuple[str, ...] = ()) -> dict[str, Any]:
    return {
        "event_id": event["id"],
        "role": event["role"],
        "kind": event["kind"],
        "occurred_at": event["occurred_at"],
        "content": [
            _block(part) for part in event["content"] if part["kind"] not in omit
        ],
    }


def _scrub_list(scrubber: Scrubber, values: list[str]) -> list[str]:
    return [
        scrubber.scrub_text(value, event_id=None, block_id=None) for value in values
    ]


def _scrub_text(scrubber: Scrubber, value: str | None) -> str | None:
    if value is None:
        return None
    return scrubber.scrub_text(value, event_id=None, block_id=None)


def build_case_record(
    detail: TaskDetail,
    conversations: dict[tuple[str, str], LoadedConversation],
    *,
    terms: list[str],
) -> CaseRecord:
    """Assemble and scrub the record for one resolved, approved task version."""
    document = detail.document
    if document.status != "approved" or document.leakage_review is None:
        raise CaseExportNotApproved(document.status)
    cut = document.cut_point
    conversation = conversations[(cut.conversation_id, cut.revision)]
    events = conversation.events
    scrubber = Scrubber(terms)

    candidate_ids = [event.event_id for event in detail.split.candidate]
    judge_ids = [event.event_id for event in detail.split.judge]
    system: list[dict[str, Any]] = []
    messages: list[dict[str, Any]] = []
    calls_before_cut = 0
    for event_id in candidate_ids:
        event = scrubber.scrub_event(events[event_id])
        calls_before_cut += sum(
            1 for part in event["content"] if part["kind"] == "tool_call"
        )
        if event["kind"] == "configuration" or event["role"] in ("system", "developer"):
            system.append(_message(event))
        else:
            messages.append(_message(event, omit=_CANDIDATE_OMITTED))
    historical = [
        _message(scrubber.scrub_event(events[event_id])) for event_id in judge_ids
    ]

    other: list[dict[str, Any]] = []
    for item in detail.split.other_judge:
        ref = next(
            bundle_item.ref
            for bundle_item in detail.bundle.items
            if bundle_item.ref.event_id == item.event_id
            and bundle_item.ref.conversation_id != cut.conversation_id
        )
        cited = conversations[(ref.conversation_id, ref.revision)]
        other.append(
            {
                "conversation_id": ref.conversation_id,
                "native_id": _scrub_text(
                    scrubber, cited.document["source"]["native_id"]
                ),
                "revision": ref.revision,
                "message": _message(scrubber.scrub_event(cited.events[item.event_id])),
            }
        )

    candidate_set = set(candidate_ids)
    cited_items = [
        {
            "conversation_id": item.ref.conversation_id,
            "event_id": item.ref.event_id,
            "block_id": item.ref.block_id,
            "text_start": item.ref.text_start,
            "text_end": item.ref.text_end,
            "role": item.role,
            "note": _scrub_text(scrubber, item.note),
            "section": "candidate"
            if item.ref.conversation_id == cut.conversation_id
            and item.ref.event_id in candidate_set
            else "judge",
        }
        for item in detail.bundle.items
    ]

    case = {
        "id": detail.id,
        "version": detail.version,
        "status": document.status,
        "kind": document.kind,
        "summary": _scrub_text(scrubber, document.summary),
        "objective": _scrub_text(scrubber, document.objective),
        "objective_type": document.objective_type,
        "lineage": {
            "source_kind": conversation.document["source"]["kind"],
            "conversation_id": cut.conversation_id,
            "native_id": _scrub_text(
                scrubber, conversation.document["source"]["native_id"]
            ),
            "revision": cut.revision,
            "bundle_id": document.bundle_id,
            "bundle_revision": document.bundle_revision,
            "family": _scrub_text(scrubber, document.family),
        },
        "cut_point": {"event_id": cut.event_id, "role": events[cut.event_id]["role"]},
        "reconstruction": {
            "level": document.reconstruction.level,
            "gaps": _scrub_list(scrubber, list(document.reconstruction.gaps)),
        },
        "criteria": [
            {
                "id": criterion.id,
                "statement": _scrub_text(scrubber, criterion.statement),
                "method": criterion.method,
                "rubric_version": criterion.rubric_version,
                "judge_evidence": list(criterion.judge_evidence),
                "reviewer_label": criterion.reviewer_label,
                "note": _scrub_text(scrubber, criterion.note),
            }
            for criterion in document.criteria
        ],
        "expected_scope": (
            None
            if document.expected_scope is None
            else document.expected_scope.model_dump(mode="json")
        ),
        "leakage_review": {
            "by": document.leakage_review.by,
            "at": document.leakage_review.at.isoformat(),
            "accepted_flags": list(document.leakage_review.accepted_flags),
        },
        "partition": document.partition,
        "redaction": {
            "scrub_version": SCRUB_VERSION,
            "term_count": scrubber.term_count,
            # Filled below, once every section has been scrubbed.
            "manifest": {},
        },
    }
    candidate = {
        "system": system,
        "messages": messages,
        "tools": {"definitions_captured": False, "calls_before_cut": calls_before_cut},
        "context": [],
        "omitted_block_kinds": list(_CANDIDATE_OMITTED),
    }
    judge = {
        "historical": historical,
        "other_conversations": other,
        "cited": cited_items,
        "bundle": {
            "rationale": _scrub_text(scrubber, detail.bundle.rationale),
            "missing_evidence": _scrub_list(
                scrubber, list(detail.bundle.missing_evidence)
            ),
        },
        "feedback": None,
        "reviewer_notes": _scrub_text(scrubber, document.reviewer_notes),
    }
    case["redaction"]["manifest"] = dict(sorted(scrubber.counts.items()))

    canonical = json.dumps(
        {"case": case, "candidate": candidate, "judge": judge},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return CaseRecord(
        case=case,
        candidate=candidate,
        judge=judge,
        digest=hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
    )


def export_case(
    session: Session, task_id: str, *, version: int | None = None, terms: list[str]
) -> CaseRecord:
    """Export one approved task version; raises for drafts and retired versions."""
    detail = get_task(session, task_id, version=version)
    review = detail.document.leakage_review
    if detail.document.status != "approved" or review is None:
        raise CaseExportNotApproved(detail.document.status)
    if any(flag.id not in review.accepted_flags for flag in detail.flags):
        # Approval checked the same flags, so this only fires if a check
        # changed since. Never export a leak the reviewer has not seen.
        raise TaskInvalid(
            (
                TaskIssue(
                    "unaccepted_leakage_flag",
                    "A leakage flag appeared after approval; review the task again.",
                ),
            )
        )
    cut = detail.document.cut_point
    refs = [item.ref for item in detail.bundle.items]
    conversations = load_conversations(
        session, [*refs, EvidenceRef(**cut.model_dump())]
    )
    return build_case_record(detail, conversations, terms=terms)
