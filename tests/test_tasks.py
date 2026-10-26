"""Shape rules of task documents, independent of any stored conversation."""

from __future__ import annotations

import datetime as dt
from typing import Any

from pydantic import ValidationError
import pytest

from benchwarmer.tasks import Criterion, LeakageReview, TaskDocument


def _document(**overrides: Any) -> dict[str, Any]:
    return {
        "bundle_id": "bundle-1",
        "bundle_revision": 1,
        "kind": "chat",
        "family": "conversation-1",
        "cut_point": {"conversation_id": "c1", "revision": "r1", "event_id": "e1"},
        "reconstruction": {"level": "prompt_only", "gaps": []},
    } | overrides


def _criterion(**overrides: Any) -> dict[str, Any]:
    return {
        "id": "states-assumption",
        "statement": "States the assumption before acting on it.",
        "method": "human",
    } | overrides


def test_deterministic_criteria_read_no_judge_evidence() -> None:
    with pytest.raises(ValidationError, match="reads no judge evidence"):
        Criterion.model_validate(
            _criterion(method="deterministic", judge_evidence=["judge.historical"])
        )
    assert (
        Criterion.model_validate(
            _criterion(method="llm_judge", judge_evidence=["judge.historical"])
        ).rubric_version
        == 1
    )


def test_only_human_criteria_carry_a_reviewer_label() -> None:
    with pytest.raises(ValidationError, match="only a human criterion"):
        Criterion.model_validate(_criterion(method="llm_judge", reviewer_label="pass"))
    assert Criterion.model_validate(_criterion(reviewer_label="unsure")).reviewer_label


def test_criterion_ids_are_slugs_and_unique() -> None:
    with pytest.raises(ValidationError):
        Criterion.model_validate(_criterion(id="Not A Slug"))
    with pytest.raises(ValidationError, match="unique"):
        TaskDocument.model_validate(_document(criteria=[_criterion(), _criterion()]))


def test_expected_scope_is_for_coding_tasks() -> None:
    scope = {"in_scope_paths": ["src/**"], "approval_paths": [], "excluded_paths": []}
    with pytest.raises(ValidationError, match="coding tasks only"):
        TaskDocument.model_validate(_document(expected_scope=scope))
    document = TaskDocument.model_validate(
        _document(kind="coding", expected_scope=scope)
    )
    assert document.expected_scope is not None


def test_approval_needs_criteria_objective_and_a_leakage_review() -> None:
    review = LeakageReview(by="reviewer", at=dt.datetime(2026, 10, 26, tzinfo=dt.UTC))
    with pytest.raises(ValidationError, match="at least one criterion"):
        TaskDocument.model_validate(_document(status="approved"))
    with pytest.raises(ValidationError, match="needs an objective"):
        TaskDocument.model_validate(
            _document(status="approved", criteria=[_criterion()])
        )
    with pytest.raises(ValidationError, match="needs a leakage review"):
        TaskDocument.model_validate(
            _document(
                status="approved", objective="explain a thing", criteria=[_criterion()]
            )
        )
    approved = TaskDocument.model_validate(
        _document(
            status="approved",
            objective="explain a thing",
            criteria=[_criterion()],
            leakage_review=review.model_dump(),
        )
    )
    assert approved.leakage_review == review
