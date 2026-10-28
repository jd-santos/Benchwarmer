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


def _task_with_family(
    client: TestClient, draft: dict[str, Any], family: str, **overrides: Any
) -> str:
    document = dict(draft, family=family) | overrides
    response = client.post("/api/v1/tasks", json={"document": document})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_partitions_are_assigned_by_family_and_each_run_is_recorded(
    client: TestClient,
) -> None:
    detail = _conversation(client, "demo-import-duplicates")
    bundle = _reviewed_bundle(client, detail)
    draft = client.get(f"/api/v1/bundles/{bundle['id']}/task-draft").json()["document"]
    assert client.get("/api/v1/tasks/partitions").json() is None

    a1 = _task_with_family(client, draft, "family-a")
    a2 = _task_with_family(client, draft, "family-a", partition="holdout")
    b = _task_with_family(client, draft, "family-b")
    retired = _task_with_family(client, draft, "family-c")
    client.put(
        f"/api/v1/tasks/{retired}",
        json={
            "document": dict(draft, family="family-c", status="retired"),
            "base_version": 1,
        },
    )

    response = client.post("/api/v1/tasks/partitions", json={"seed": "autumn-1"})
    assert response.status_code == 201, response.text
    run = response.json()
    assert run["seed"] == "autumn-1"
    assert run["split"] == {"development": 0.6, "calibration": 0.2, "holdout": 0.2}
    assert run["scope"] == {"statuses": ["draft", "approved"]}
    assert run["task_count"] == 3 and run["family_count"] == 2
    assert sum(run["task_counts"].values()) == 3
    assert sum(run["family_counts"].values()) == 2
    assert run["moved_families"] == 0

    listed = {item["id"]: item for item in client.get("/api/v1/tasks").json()["items"]}
    # One family, one side: the hand-set legacy field on a2 no longer decides.
    assert listed[a1]["partition"] == listed[a2]["partition"] is not None
    assert listed[a1]["partition_assignment_id"] == run["id"]
    assert listed[b]["partition"] is not None
    assert listed[retired]["partition"] is None
    assert listed[retired]["partition_assignment_id"] is None
    task_detail = client.get(f"/api/v1/tasks/{a2}").json()
    assert task_detail["partition"] == listed[a2]["partition"]
    assert task_detail["document"]["partition"] == "holdout"

    assert client.get("/api/v1/tasks/partitions").json()["id"] == run["id"]

    # Deterministic: the same seed over the same families changes nothing.
    again = client.post("/api/v1/tasks/partitions", json={"seed": "autumn-1"}).json()
    assert again["id"] != run["id"]
    assert again["task_counts"] == run["task_counts"] and again["moved_families"] == 0
    relisted = {
        item["id"]: item for item in client.get("/api/v1/tasks").json()["items"]
    }
    assert {k: v["partition"] for k, v in relisted.items()} == {
        k: v["partition"] for k, v in listed.items()
    }
    assert relisted[a1]["partition_assignment_id"] == again["id"]

    # Scope and split are honored; a split that is not a split is refused.
    everything = client.post(
        "/api/v1/tasks/partitions",
        json={
            "seed": "autumn-1",
            "split": {"development": 0, "calibration": 0, "holdout": 1},
            "scope": {"statuses": ["draft", "approved", "retired"]},
        },
    ).json()
    assert everything["task_count"] == 4 and everything["family_count"] == 3
    assert everything["family_counts"] == {
        "development": 0,
        "calibration": 0,
        "holdout": 3,
    }
    assert everything["moved_families"] >= 1
    assert all(
        item["partition"] == "holdout"
        for item in client.get("/api/v1/tasks").json()["items"]
    )
    bad = client.post(
        "/api/v1/tasks/partitions",
        json={
            "seed": "x",
            "split": {"development": 0.5, "calibration": 0.5, "holdout": 0.5},
        },
    )
    assert bad.status_code == 422 and "sum to 1" in bad.json()["detail"]


def test_export_reports_the_assigned_partition(client: TestClient) -> None:
    detail = _conversation(client, "demo-import-duplicates")
    bundle = _reviewed_bundle(client, detail)
    draft = client.get(f"/api/v1/bundles/{bundle['id']}/task-draft").json()["document"]
    approved = dict(
        draft,
        status="approved",
        partition="development",
        criteria=[_criterion()],
        leakage_review=_REVIEW,
    )
    task_id = client.post("/api/v1/tasks", json={"document": approved}).json()["id"]

    before = client.post(f"/api/v1/tasks/{task_id}/export", json={"terms": []}).json()
    assert before["case"]["partition"] == "development"
    assert before["case"]["partition_assignment_id"] is None
    assert before["case"]["criteria"][0]["needs"] == []

    run = client.post(
        "/api/v1/tasks/partitions",
        json={"seed": "s", "split": {"development": 0, "calibration": 1, "holdout": 0}},
    ).json()
    after = client.post(f"/api/v1/tasks/{task_id}/export", json={"terms": []}).json()
    assert after["case"]["partition"] == "calibration"
    assert after["case"]["partition_assignment_id"] == run["id"]
    assert after["digest"] != before["digest"]
    # The approved version's content did not change; it is still version 1.
    assert client.get(f"/api/v1/tasks/{task_id}").json()["latest_version"] == 1


def test_approval_refuses_needs_the_reconstruction_cannot_meet(
    client: TestClient,
) -> None:
    detail = _conversation(client, "demo-import-duplicates")
    bundle = _reviewed_bundle(client, detail)
    draft = client.get(f"/api/v1/bundles/{bundle['id']}/task-draft").json()["document"]
    needs_tools = _criterion(needs=["tools"])
    approved = dict(
        draft, status="approved", criteria=[needs_tools], leakage_review=_REVIEW
    )

    refused = client.post("/api/v1/tasks", json={"document": approved})
    assert refused.status_code == 422, refused.text
    (issue,) = refused.json()["issues"]
    assert issue["code"] == "needs_exceed_reconstruction"
    assert issue["criterion_id"] == "diagnose-overlap"
    assert "prompt_only" in issue["message"]

    coding = dict(approved, kind="coding", criteria=[_criterion()])
    refused = client.post("/api/v1/tasks", json={"document": coding})
    (issue,) = refused.json()["issues"]
    assert issue["code"] == "needs_exceed_reconstruction"
    assert issue["criterion_id"] is None and "workspace" in issue["message"]

    # As a draft it stays usable as analysis-only evidence, and says so.
    as_draft = client.post(
        "/api/v1/tasks", json={"document": dict(approved, status="draft")}
    )
    assert as_draft.status_code == 201, as_draft.text
    assert as_draft.json()["unmet_needs"] == [
        {"criterion_id": "diagnose-overlap", "needs": ["tools"]}
    ]
    listed = client.get("/api/v1/tasks").json()["items"]
    assert [item["analysis_only"] for item in listed] == [True]

    # A fixture-backed reconstruction provides tools, so the same task approves.
    backed = dict(approved, reconstruction={"level": "fixture_backed", "gaps": []})
    response = client.post("/api/v1/tasks", json={"document": backed})
    assert response.status_code == 201, response.text
    assert response.json()["unmet_needs"] == []
    assert response.json()["document"]["status"] == "approved"
