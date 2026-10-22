"""Evidence bundles over the synthetic demo conversations."""

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
    detail: dict[str, Any], native_id: str, block: int | None = None, **extra: int
) -> dict[str, Any]:
    event = _event(detail, native_id)
    return {
        "conversation_id": detail["summary"]["id"],
        "revision": detail["summary"]["revision"],
        "event_id": event["id"],
        "block_id": event["content"][block]["id"] if block is not None else None,
        **extra,
    }


def _issues(response: Any) -> list[str]:
    assert response.status_code == 422, response.text
    return [issue["code"] for issue in response.json()["issues"]]


def test_create_resolves_events_blocks_and_text_ranges(client: TestClient) -> None:
    detail = _conversation(client, "demo-import-duplicates")
    question = _event(detail, "u0")["content"][0]["text"]
    document = {
        "objective": "Find why duplicate sessions appear",
        "items": [
            {"ref": _ref(detail, "u0"), "role": "requirement"},
            {
                "ref": _ref(detail, "a2", 1, text_start=0, text_end=14),
                "role": "result",
                "note": "Overlap explains it",
            },
            {"ref": _ref(detail, "t4", 0), "role": "result"},
        ],
    }

    response = client.post("/api/v1/bundles", json={"document": document})

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["revision"] == 1 and body["origin"] == "human"
    first, second, third = body["items"]
    assert first["excerpt"] == question
    assert first["event_role"] == "user" and first["omitted_before"] is None
    assert second["excerpt"] == "Here are the r"
    assert second["block_kind"] == "text" and second["omitted_before"] > 0
    assert third["block_kind"] == "tool_result"
    assert first["conversation_is_latest"] is True


def test_revisions_conflicts_and_unchanged_saves(client: TestClient) -> None:
    detail = _conversation(client, "demo-import-duplicates")
    document = {"items": [{"ref": _ref(detail, "u0"), "role": "context"}]}
    created = client.post("/api/v1/bundles", json={"document": document}).json()
    bundle_id = created["id"]

    unchanged = client.put(
        f"/api/v1/bundles/{bundle_id}",
        json={"document": created["document"], "base_revision": 1},
    )
    assert unchanged.json()["revision"] == 1

    revised = dict(created["document"], objective="Duplicates", status="reviewed")
    updated = client.put(
        f"/api/v1/bundles/{bundle_id}",
        json={"document": revised, "base_revision": 1},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["revision"] == 2
    assert [item["number"] for item in updated.json()["revisions"]] == [2, 1]

    stale = client.put(
        f"/api/v1/bundles/{bundle_id}",
        json={"document": revised | {"objective": "Other"}, "base_revision": 1},
    )
    assert stale.status_code == 409
    assert stale.json()["latest_revision"] == 2

    earlier = client.get(f"/api/v1/bundles/{bundle_id}", params={"revision": 1})
    assert earlier.json()["document"]["objective"] == ""
    assert earlier.json()["latest_revision"] == 2

    listed = client.get(
        "/api/v1/bundles", params={"conversation_id": detail["summary"]["id"]}
    ).json()["items"]
    assert [(item["id"], item["status"]) for item in listed] == [
        (bundle_id, "reviewed")
    ]
    other = _conversation(client, "demo-ruff-flag")["summary"]["id"]
    assert client.get("/api/v1/bundles", params={"conversation_id": other}).json() == {
        "items": []
    }


def test_rejects_sibling_branches_and_unrelated_conversations(
    client: TestClient,
) -> None:
    detail = _conversation(client, "demo-import-duplicates")
    sibling = {
        "items": [
            {"ref": _ref(detail, "u4"), "role": "requirement"},
            {"ref": _ref(detail, "alt-u"), "role": "requirement"},
        ]
    }
    assert "sibling_branches" in _issues(
        client.post("/api/v1/bundles", json={"document": sibling})
    )

    other = _conversation(client, "demo-ruff-flag")
    unrelated = {
        "items": [
            {"ref": _ref(detail, "u0"), "role": "requirement"},
            {"ref": _ref(other, "q1"), "role": "requirement"},
        ]
    }
    assert _issues(client.post("/api/v1/bundles", json={"document": unrelated})) == [
        "unrelated_conversations"
    ]


def test_accepts_evidence_across_a_captured_continuation(client: TestClient) -> None:
    earlier = _conversation(client, "demo-migration-1")
    later = _conversation(client, "demo-migration-2")
    document = {
        "items": [
            {"ref": _ref(earlier, "m1"), "role": "requirement"},
            {"ref": _ref(later, "n2"), "role": "action"},
        ]
    }
    response = client.post("/api/v1/bundles", json={"document": document})
    assert response.status_code == 201, response.text
    missing_text = _ref(earlier, "m2")
    assert response.json()["items"][0]["excerpt"].startswith("Plan the migration")

    gap = client.post(
        "/api/v1/bundles",
        json={"document": {"items": [{"ref": missing_text, "role": "action"}]}},
    )
    assert gap.status_code == 201
    assert gap.json()["items"][0]["excerpt"] is None


def test_rejects_unresolvable_references(client: TestClient) -> None:
    detail = _conversation(client, "demo-import-duplicates")
    older = detail["revisions"][1]["revision"]
    cases = {
        "event_not_found": _ref(detail, "u0") | {"event_id": "missing"},
        "block_not_found": _ref(detail, "u0") | {"block_id": "missing"},
        "range_out_of_bounds": _ref(detail, "u0", 0, text_start=0, text_end=100_000),
        "conversation_not_found": _ref(detail, "u0") | {"revision": "0" * 64},
    }
    for code, ref in cases.items():
        response = client.post(
            "/api/v1/bundles",
            json={"document": {"items": [{"ref": ref, "role": "context"}]}},
        )
        assert _issues(response) == [code]

    mixed = {
        "items": [
            {"ref": _ref(detail, "u0"), "role": "context"},
            {"ref": _ref(detail, "u1") | {"revision": older}, "role": "context"},
        ]
    }
    assert _issues(client.post("/api/v1/bundles", json={"document": mixed})) == [
        "mixed_revisions"
    ]


def test_rejects_malformed_documents(client: TestClient) -> None:
    detail = _conversation(client, "demo-import-duplicates")
    ref = _ref(detail, "u0")
    malformed = [
        {"items": []},
        {"status": "reviewed", "items": [{"ref": ref, "role": "context"}]},
        {"items": [{"ref": ref | {"text_start": 3}, "role": "context"}]},
        {"items": [{"ref": ref | {"text_start": 0, "text_end": 2}, "role": "context"}]},
        {"items": [{"ref": ref, "role": "context"}, {"ref": ref, "role": "action"}]},
        {"items": [{"ref": ref, "role": "verdict"}]},
    ]
    for document in malformed:
        response = client.post("/api/v1/bundles", json={"document": document})
        assert response.status_code == 422, document

    assert client.get("/api/v1/bundles/missing").status_code == 404
    assert (
        client.put(
            "/api/v1/bundles/missing",
            json={
                "document": {"items": [{"ref": ref, "role": "context"}]},
                "base_revision": 1,
            },
        ).status_code
        == 404
    )


def test_generated_bundles_record_origin_and_producer(client: TestClient) -> None:
    detail = _conversation(client, "demo-import-duplicates")
    document = {
        "objective": "Proposed by a harness run",
        "items": [{"ref": _ref(detail, "u0"), "role": "requirement"}],
        "rationale": "Pilot proposal",
    }

    created = client.post(
        "/api/v1/bundles",
        json={
            "document": document,
            "origin": "generated",
            "producer": "benchwarmer-harness/propose-bundles@0.0.1 anthropic/test",
        },
    )

    assert created.status_code == 201, created.text
    body = created.json()
    assert body["origin"] == "generated"
    assert body["producer"].startswith("benchwarmer-harness/propose-bundles")
    assert body["document"]["status"] == "draft"

    corrected = client.put(
        f"/api/v1/bundles/{body['id']}",
        json={
            "document": dict(document, status="reviewed"),
            "base_revision": 1,
        },
    )
    assert corrected.status_code == 200, corrected.text
    revisions = corrected.json()["revisions"]
    assert [(r["number"], r["origin"]) for r in revisions] == [
        (2, "human"),
        (1, "generated"),
    ]

    rejected = client.post(
        "/api/v1/bundles",
        json={"document": document, "origin": "generated", "producer": ""},
    )
    assert rejected.status_code == 422


def test_lists_provenance_and_filters_proposed_drafts(client: TestClient) -> None:
    detail = _conversation(client, "demo-import-duplicates")
    document = {"items": [{"ref": _ref(detail, "u0"), "role": "requirement"}]}
    producer = "benchwarmer-harness/propose-bundles@0.0.1 anthropic/test"
    proposed = client.post(
        "/api/v1/bundles",
        json={"document": document, "origin": "generated", "producer": producer},
    ).json()
    human = client.post("/api/v1/bundles", json={"document": document}).json()

    listed = client.get("/api/v1/bundles").json()["items"]
    by_id = {item["id"]: item for item in listed}
    assert by_id[proposed["id"]]["origin"] == "generated"
    assert by_id[proposed["id"]]["producer"] == producer
    assert by_id[human["id"]] | {} == by_id[human["id"]] | {
        "origin": "human",
        "producer": "web",
    }

    pending = client.get(
        "/api/v1/bundles", params={"origin": "generated", "status": "draft"}
    ).json()["items"]
    assert [item["id"] for item in pending] == [proposed["id"]]

    # A rejection keeps the proposal queryable and must say why.
    unexplained = client.put(
        f"/api/v1/bundles/{proposed['id']}",
        json={"document": dict(document, status="rejected"), "base_revision": 1},
    )
    assert unexplained.status_code == 422
    rejected = client.put(
        f"/api/v1/bundles/{proposed['id']}",
        json={
            "document": dict(
                document, status="rejected", rationale="Two unrelated requests"
            ),
            "base_revision": 1,
        },
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["origin"] == "human"
    assert (
        client.get("/api/v1/bundles", params={"origin": "generated"}).json()["items"]
        == []
    )
    kept = client.get("/api/v1/bundles", params={"status": "rejected"}).json()
    assert [item["id"] for item in kept["items"]] == [proposed["id"]]
    assert client.get("/api/v1/bundles", params={"origin": "robot"}).status_code == 422


def test_generated_bundles_carry_run_provenance_and_idempotent_creation(
    client: TestClient,
) -> None:
    detail = _conversation(client, "demo-import-duplicates")
    document = {"items": [{"ref": _ref(detail, "u0"), "role": "requirement"}]}
    provenance = {
        "run_id": "propose-bundles-2026-10-21T00-00-00Z",
        "workflow": "propose-bundles",
        "harness_version": "0.0.1",
        "provider": "anthropic",
        "model": "test-model",
        "thinking_level": None,
        "report_path": "reports/harness/propose-bundles-2026-10-21T00-00-00Z.json",
    }
    request = {
        "document": document,
        "origin": "generated",
        "producer": "benchwarmer-harness/propose-bundles@0.0.1 anthropic/test-model",
        "provenance": provenance,
        "request_id": "propose-bundles-2026-10-21T00-00-00Z:conv:1",
    }

    first = client.post("/api/v1/bundles", json=request)
    assert first.status_code == 201, first.text
    assert first.json()["provenance"] == provenance
    assert first.json()["request_id"] == request["request_id"]
    assert first.json()["revisions"][0]["provenance"]["run_id"] == provenance["run_id"]

    # The same request id returns the same bundle rather than a second one.
    again = client.post("/api/v1/bundles", json=dict(request, document=document))
    assert again.status_code == 200, again.text
    assert again.json()["id"] == first.json()["id"]
    listed = client.get(
        "/api/v1/bundles", params={"run_id": provenance["run_id"]}
    ).json()["items"]
    assert [(item["id"], item["run_id"]) for item in listed] == [
        (first.json()["id"], provenance["run_id"])
    ]

    # A human correction has no run provenance, and leaves the run filter.
    reviewed = client.put(
        f"/api/v1/bundles/{first.json()['id']}",
        json={
            "document": dict(document, objective="Checked", status="reviewed"),
            "base_revision": 1,
        },
    )
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["provenance"] is None
    assert reviewed.json()["revisions"][1]["provenance"]["model"] == "test-model"
    assert client.get(
        "/api/v1/bundles", params={"run_id": provenance["run_id"]}
    ).json() == {"items": []}

    # Provenance is validated as a typed record.
    malformed = client.post(
        "/api/v1/bundles",
        json=dict(request, request_id="other", provenance={"run_id": "x"}),
    )
    assert malformed.status_code == 422


def test_goal_and_objective_are_separate_and_version_1_upgrades(
    client: TestClient,
) -> None:
    detail = _conversation(client, "demo-import-duplicates")
    items = [{"ref": _ref(detail, "u0"), "role": "requirement"}]
    created = client.post(
        "/api/v1/bundles",
        json={
            "document": {
                "objective": "Diagnose duplicate records from a scheduled import",
                "goal": "Find why duplicate sessions appear after the nightly import",
                "items": items,
            }
        },
    )
    assert created.status_code == 201, created.text
    document = created.json()["document"]
    assert document["schema_version"] == 2
    assert document["goal"].startswith("Find why")
    listed = client.get("/api/v1/bundles").json()["items"]
    assert listed[0]["goal"] == document["goal"]
    assert listed[0]["objective"] == document["objective"]

    # A reviewed bundle needs the general objective; a goal alone is not enough.
    goal_only = client.put(
        f"/api/v1/bundles/{created.json()['id']}",
        json={
            "document": {"goal": "Specific aim", "status": "reviewed", "items": items},
            "base_revision": 1,
        },
    )
    assert goal_only.status_code == 422

    # Version 1 documents kept the specific aim in objective; it becomes the goal
    # and stays in objective until a reviewer generalizes it.
    legacy = client.post(
        "/api/v1/bundles",
        json={
            "document": {
                "schema_version": 1,
                "objective": "Find why duplicate sessions appear",
                "items": items,
            }
        },
    )
    assert legacy.status_code == 201, legacy.text
    assert legacy.json()["document"] | {} == legacy.json()["document"] | {
        "schema_version": 2,
        "goal": "Find why duplicate sessions appear",
        "objective": "Find why duplicate sessions appear",
    }
    assert (
        client.post(
            "/api/v1/bundles",
            json={"document": {"schema_version": 3, "items": items}},
        ).status_code
        == 422
    )
