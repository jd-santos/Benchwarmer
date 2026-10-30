"""Task versions and case export over the synthetic demo conversations."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
from typing import Any

from fastapi.testclient import TestClient
import pytest

from benchwarmer.api.app import create_app
from benchwarmer.config import BenchwarmerSettings
from benchwarmer.services.demo_conversations import load_demo_conversations
from benchwarmer.services.fixtures import load_fixture

_REPOSITORY_ROOT = Path(__file__).parents[2]
_FIXTURE = _REPOSITORY_ROOT / "tests" / "fixtures" / "demo-conversations.json"
_REVIEW = {"by": "reviewer", "at": "2026-10-26T12:00:00+00:00", "accepted_flags": []}


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    root = tmp_path / "private"
    result = subprocess.run(
        ["uv", "run", "alembic", "upgrade", "head"],
        cwd=_REPOSITORY_ROOT,
        env=os.environ | {"BENCHWARMER_DATA_ROOT": str(root)},
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    settings = BenchwarmerSettings(data_root=root)
    load_fixture(settings, _REPOSITORY_ROOT / "tests" / "fixtures" / "sources.json")
    load_demo_conversations(settings, _FIXTURE)
    return TestClient(create_app(settings=settings))


def _conversation(client: TestClient, native_id: str) -> dict[str, Any]:
    page = client.get("/api/v1/conversations").json()
    summary = next(item for item in page["items"] if item["native_id"] == native_id)
    return client.get(f"/api/v1/conversations/{summary['id']}").json()


def _event(detail: dict[str, Any], native_id: str) -> dict[str, Any]:
    return next(item for item in detail["events"] if item["native_id"] == native_id)


def _ref(
    detail: dict[str, Any], native_id: str, block: int | None = None
) -> dict[str, Any]:
    event = _event(detail, native_id)
    return {
        "conversation_id": detail["summary"]["id"],
        "revision": detail["summary"]["revision"],
        "event_id": event["id"],
        "block_id": event["content"][block]["id"] if block is not None else None,
    }


def _text(detail: dict[str, Any], native_id: str) -> str:
    event = _event(detail, native_id)
    return next(part["text"] for part in event["content"] if part["kind"] == "text")


def _reviewed_bundle(client: TestClient, detail: dict[str, Any]) -> dict[str, Any]:
    """A bundle citing the question, the overlap answer, and the test result."""
    document = {
        "summary": "Duplicate sessions traced to overlapping batches.",
        "objective": "diagnose duplicate records from a scheduled import",
        "objective_type": "bug",
        "status": "reviewed",
        "items": [
            {"ref": _ref(detail, "u0"), "role": "requirement"},
            {"ref": _ref(detail, "a2", 1), "role": "result", "note": "The answer"},
            {"ref": _ref(detail, "t4"), "role": "result"},
        ],
        "missing_evidence": ["The import log for the first night was not captured."],
    }
    response = client.post("/api/v1/bundles", json={"document": document})
    assert response.status_code == 201, response.text
    return response.json()


def _issues(response: Any) -> list[str]:
    assert response.status_code == 422, response.text
    return [issue["code"] for issue in response.json()["issues"]]


def _criterion(**overrides: Any) -> dict[str, Any]:
    return {
        "id": "diagnose-overlap",
        "statement": "Checks whether import windows overlap before blaming the data.",
        "method": "llm_judge",
        "rubric_version": 1,
        "judge_evidence": ["judge.historical"],
        "reviewer_label": None,
        "note": None,
    } | overrides


def test_draft_proposes_cut_before_the_first_cited_answer(client: TestClient) -> None:
    detail = _conversation(client, "demo-import-duplicates")
    bundle = _reviewed_bundle(client, detail)

    response = client.get(f"/api/v1/bundles/{bundle['id']}/task-draft")

    assert response.status_code == 200, response.text
    draft = response.json()
    document = draft["document"]
    assert document["bundle_id"] == bundle["id"] and document["bundle_revision"] == 1
    assert document["kind"] == "agent"
    assert document["summary"] == bundle["document"]["summary"]
    assert document["objective_type"] == "bug"
    assert document["family"] == detail["summary"]["id"]
    # The last user turn before the cited answer in a2.
    assert document["cut_point"]["event_id"] == _event(detail, "u2")["id"]
    assert document["reconstruction"] == {
        "level": "prompt_only",
        "gaps": ["The import log for the first night was not captured."],
    }
    assert document["status"] == "draft" and document["criteria"] == []
    split = draft["split"]
    candidate = [item["event_id"] for item in split["candidate"]]
    judge = [item["event_id"] for item in split["judge"]]
    assert candidate == [
        _event(detail, n)["id"] for n in ("u0", "a0", "t0", "u1", "a1", "t1", "u2")
    ]
    assert (
        judge[0] == _event(detail, "a2")["id"]
        and judge[-1] == _event(detail, "t4")["id"]
    )
    assert split["candidate"][0]["cited_as"] == ["requirement"]
    assert split["judge"][0]["cited_as"] == ["result"]
    assert split["other_judge"] == []
    assert draft["flags"] == []
    assert draft["bundle"]["status"] == "reviewed"
    assert client.get("/api/v1/bundles/missing/task-draft").status_code == 404


def test_flags_name_answers_before_the_cut_and_quoted_criteria(
    client: TestClient,
) -> None:
    detail = _conversation(client, "demo-import-duplicates")
    bundle = _reviewed_bundle(client, detail)
    draft = client.get(f"/api/v1/bundles/{bundle['id']}/task-draft").json()["document"]
    answer = _text(detail, "a2")

    before_cut = dict(
        draft,
        cut_point=dict(draft["cut_point"], event_id=_event(detail, "t2")["id"]),
    )
    created = client.post("/api/v1/tasks", json={"document": before_cut})

    assert created.status_code == 201, created.text
    (flag,) = created.json()["flags"]
    assert flag["id"] == "answer_before_cut:1" and flag["item_index"] == 1
    assert flag["event_id"] == _event(detail, "a2")["id"]

    quoted = dict(draft, criteria=[_criterion(statement=" ".join(answer.split()[:12]))])
    response = client.post("/api/v1/tasks", json={"document": quoted})
    assert response.status_code == 201, response.text
    (flag,) = response.json()["flags"]
    assert flag["id"] == "criterion_quotes_answer:diagnose-overlap"
    assert flag["criterion_id"] == "diagnose-overlap"

    after_assistant = dict(
        draft, cut_point=dict(draft["cut_point"], event_id=_event(detail, "a6")["id"])
    )
    response = client.post("/api/v1/tasks", json={"document": after_assistant})
    assert response.status_code == 201, response.text
    # Both cited answers now sit before the cut as well.
    assert sorted(flag["code"] for flag in response.json()["flags"]) == [
        "answer_before_cut",
        "answer_before_cut",
        "cut_after_assistant",
        "no_historical_answer",
    ]

    off_path = dict(
        draft,
        cut_point=dict(draft["cut_point"], event_id=_event(detail, "alt-a")["id"]),
    )
    assert _issues(client.post("/api/v1/tasks", json={"document": off_path})) == [
        "cut_point_off_path"
    ]


def test_approval_needs_a_reviewed_bundle_and_accepted_flags(
    client: TestClient,
) -> None:
    detail = _conversation(client, "demo-import-duplicates")
    bundle = _reviewed_bundle(client, detail)
    draft = client.get(f"/api/v1/bundles/{bundle['id']}/task-draft").json()["document"]
    approved = dict(
        draft, status="approved", criteria=[_criterion()], leakage_review=_REVIEW
    )

    # The request model rejects an approved task with no leakage review.
    missing_review = client.post(
        "/api/v1/tasks", json={"document": dict(approved, leakage_review=None)}
    )
    assert missing_review.status_code == 422

    flagged = dict(
        approved,
        cut_point=dict(draft["cut_point"], event_id=_event(detail, "t2")["id"]),
    )
    assert _issues(client.post("/api/v1/tasks", json={"document": flagged})) == [
        "unaccepted_leakage_flag"
    ]
    accepted = dict(
        flagged, leakage_review=_REVIEW | {"accepted_flags": ["answer_before_cut:1"]}
    )
    response = client.post("/api/v1/tasks", json={"document": accepted})
    assert response.status_code == 201, response.text
    assert response.json()["document"]["status"] == "approved"

    unreviewed = client.post(
        "/api/v1/bundles",
        json={"document": dict(bundle["document"], status="draft")},
    ).json()
    unreviewed_draft = client.get(
        f"/api/v1/bundles/{unreviewed['id']}/task-draft"
    ).json()
    response = client.post(
        "/api/v1/tasks",
        json={
            "document": dict(
                unreviewed_draft["document"],
                status="approved",
                criteria=[_criterion()],
                leakage_review=_REVIEW,
            )
        },
    )
    assert _issues(response) == ["bundle_not_reviewed"]


def test_versions_are_immutable_once_approved_and_retired_is_terminal(
    client: TestClient,
) -> None:
    detail = _conversation(client, "demo-import-duplicates")
    bundle = _reviewed_bundle(client, detail)
    draft = client.get(f"/api/v1/bundles/{bundle['id']}/task-draft").json()["document"]
    created = client.post("/api/v1/tasks", json={"document": draft}).json()
    task_id = created["id"]

    unchanged = client.put(
        f"/api/v1/tasks/{task_id}", json={"document": draft, "base_version": 1}
    )
    assert unchanged.json()["version"] == 1

    approved = dict(
        draft, status="approved", criteria=[_criterion()], leakage_review=_REVIEW
    )
    response = client.put(
        f"/api/v1/tasks/{task_id}", json={"document": approved, "base_version": 1}
    )
    assert response.status_code == 200, response.text
    assert response.json()["version"] == 2
    assert [(v["number"], v["status"]) for v in response.json()["versions"]] == [
        (2, "approved"),
        (1, "draft"),
    ]

    stale = client.put(
        f"/api/v1/tasks/{task_id}", json={"document": approved, "base_version": 1}
    )
    assert stale.status_code == 409 and stale.json()["latest_version"] == 2

    changed = dict(approved, criteria=[_criterion(rubric_version=2)])
    assert _issues(
        client.put(
            f"/api/v1/tasks/{task_id}", json={"document": changed, "base_version": 2}
        )
    ) == ["approved_content_changed"]

    redrafted = client.put(
        f"/api/v1/tasks/{task_id}",
        json={"document": dict(changed, status="draft"), "base_version": 2},
    )
    assert redrafted.status_code == 200, redrafted.text
    assert redrafted.json()["version"] == 3

    earlier = client.get(f"/api/v1/tasks/{task_id}", params={"version": 2})
    assert earlier.json()["document"]["status"] == "approved"
    assert earlier.json()["latest_version"] == 3

    retired = client.put(
        f"/api/v1/tasks/{task_id}",
        json={"document": dict(changed, status="retired"), "base_version": 3},
    )
    assert retired.status_code == 200, retired.text
    assert _issues(
        client.put(
            f"/api/v1/tasks/{task_id}",
            json={"document": dict(changed, status="draft"), "base_version": 4},
        )
    ) == ["task_retired"]

    listed = client.get("/api/v1/tasks").json()["items"]
    assert [(item["id"], item["version"], item["status"]) for item in listed] == [
        (task_id, 4, "retired")
    ]
    assert (
        client.get("/api/v1/tasks", params={"status": "approved"}).json()["items"] == []
    )
    assert client.get("/api/v1/tasks/missing").status_code == 404


def test_export_splits_scrubs_and_repeats_identically(client: TestClient) -> None:
    detail = _conversation(client, "demo-import-duplicates")
    bundle = _reviewed_bundle(client, detail)
    draft = client.get(f"/api/v1/bundles/{bundle['id']}/task-draft").json()["document"]
    created = client.post("/api/v1/tasks", json={"document": draft}).json()
    task_id = created["id"]

    refused = client.post(f"/api/v1/tasks/{task_id}/export", json={"terms": []})
    assert refused.status_code == 409 and refused.json()["status"] == "draft"

    approved = dict(
        draft,
        status="approved",
        partition="development",
        criteria=[
            _criterion(),
            _criterion(
                id="no-schema-change",
                statement="Does not alter the import tables while diagnosing.",
                method="human",
                judge_evidence=[],
                reviewer_label="pass",
            ),
        ],
        leakage_review=_REVIEW,
        reviewer_notes="Hermes sessions were the symptom, not the cause.",
    )
    client.put(
        f"/api/v1/tasks/{task_id}", json={"document": approved, "base_version": 1}
    )

    response = client.post(
        f"/api/v1/tasks/{task_id}/export", json={"terms": ["Hermes"]}
    )
    assert response.status_code == 200, response.text
    record = response.json()
    assert record["schema_version"] == 1
    case = record["case"]
    assert (
        case["id"] == task_id and case["version"] == 2 and case["status"] == "approved"
    )
    assert case["lineage"]["bundle_id"] == bundle["id"]
    assert case["lineage"]["family"] == detail["summary"]["id"]
    assert case["cut_point"] == {"event_id": _event(detail, "u2")["id"], "role": "user"}
    assert [c["id"] for c in case["criteria"]] == [
        "diagnose-overlap",
        "no-schema-change",
    ]
    assert case["criteria"][1]["reviewer_label"] == "pass"
    assert case["leakage_review"]["by"] == "reviewer"
    assert case["partition"] == "development"
    assert case["redaction"]["scrub_version"].startswith("benchwarmer.anonymize-")
    assert case["redaction"]["manifest"]["term"] >= 2
    assert "Hermes" not in response.text

    candidate = record["candidate"]
    cut_index = [e["event_id"] for e in candidate["messages"]].index(
        case["cut_point"]["event_id"]
    )
    assert cut_index == len(candidate["messages"]) - 1
    assert candidate["messages"][0]["content"][0]["text"] == (
        "Why does the nightly import report duplicate <term-1> sessions?"
    )
    assert all(
        part["kind"] != "reasoning"
        for message in candidate["messages"]
        for part in message["content"]
    )
    assert candidate["tools"] == {"definitions_captured": False, "calls_before_cut": 2}

    judge = record["judge"]
    assert judge["historical"][0]["event_id"] == _event(detail, "a2")["id"]
    assert any(
        part["kind"] == "reasoning" for part in judge["historical"][0]["content"]
    )
    assert [item["section"] for item in judge["cited"]] == [
        "candidate",
        "judge",
        "judge",
    ]
    assert judge["bundle"]["missing_evidence"] == [
        "The import log for the first night was not captured."
    ]
    assert (
        judge["reviewer_notes"] == "<term-1> sessions were the symptom, not the cause."
    )

    again = client.post(f"/api/v1/tasks/{task_id}/export", json={"terms": ["Hermes"]})
    assert again.json() == record

    without_terms = client.post(f"/api/v1/tasks/{task_id}/export", json={"terms": []})
    assert without_terms.json()["digest"] != record["digest"]
    assert "term" not in without_terms.json()["case"]["redaction"]["manifest"]
    assert record["case"]["redaction"]["term_list"] is None


def test_export_takes_terms_from_a_stored_list(client: TestClient) -> None:
    detail = _conversation(client, "demo-import-duplicates")
    bundle = _reviewed_bundle(client, detail)
    draft = client.get(f"/api/v1/bundles/{bundle['id']}/task-draft").json()["document"]
    task_id = client.post("/api/v1/tasks", json={"document": draft}).json()["id"]
    approved = dict(
        draft,
        status="approved",
        criteria=[_criterion()],
        leakage_review=_REVIEW,
        reviewer_notes="Hermes sessions were the symptom; ask Wexley about it.",
    )
    client.put(
        f"/api/v1/tasks/{task_id}", json={"document": approved, "base_version": 1}
    )
    client.put("/api/v1/scrub-terms/program", json={"terms": ["Hermes"]})
    client.put("/api/v1/scrub-terms/program", json={"terms": ["Hermes", "Wexley"]})

    inline = client.post(
        f"/api/v1/tasks/{task_id}/export", json={"terms": ["Hermes", "Wexley"]}
    ).json()
    by_list = client.post(
        f"/api/v1/tasks/{task_id}/export", json={"term_list": {"name": "program"}}
    )
    assert by_list.status_code == 200, by_list.text
    record = by_list.json()
    redaction = record["case"]["redaction"]
    assert redaction["term_list"] == {"name": "program", "version": 2}
    assert redaction["term_count"] == 2 and redaction["manifest"]["term"] >= 2
    assert "Hermes" not in by_list.text and "Wexley" not in by_list.text
    assert record["judge"]["reviewer_notes"] == (
        "<term-1> sessions were the symptom; ask <term-2> about it."
    )
    # Same placeholders and sections as the inline export; only the provenance
    # under redaction differs, so the digest differs.
    assert record["judge"] == inline["judge"]
    assert record["candidate"] == inline["candidate"]
    assert record["digest"] != inline["digest"]

    # Pinned version, repeated: same bytes. Combined with an inline term: both
    # apply, and the inline term that repeats a stored one is not counted twice.
    pinned = {"term_list": {"name": "program", "version": 2}}
    first = client.post(f"/api/v1/tasks/{task_id}/export", json=pinned)
    second = client.post(f"/api/v1/tasks/{task_id}/export", json=pinned)
    assert first.json() == second.json() == record
    older = client.post(
        f"/api/v1/tasks/{task_id}/export",
        json={"term_list": {"name": "program", "version": 1}, "terms": ["hermes"]},
    ).json()
    assert older["case"]["redaction"]["term_list"]["version"] == 1
    assert older["case"]["redaction"]["term_count"] == 1
    assert "Wexley" in older["judge"]["reviewer_notes"]

    # A retired list still resolves when pinned, so old records reproduce.
    client.post("/api/v1/scrub-terms/program/retire")
    assert client.post(f"/api/v1/tasks/{task_id}/export", json=pinned).json() == record

    missing = client.post(
        f"/api/v1/tasks/{task_id}/export", json={"term_list": {"name": "nope"}}
    )
    assert missing.status_code == 422
    assert missing.json()["issues"][0]["code"] == "term_list_not_found"
    too_many = client.post(
        f"/api/v1/tasks/{task_id}/export",
        json={"term_list": pinned["term_list"], "terms": [f"t{i}" for i in range(199)]},
    )
    assert too_many.status_code == 422
    assert too_many.json()["issues"][0]["code"] == "too_many_terms"
