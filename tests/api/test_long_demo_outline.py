"""The long synthetic coding sessions carry the structures the outline measures."""

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
_FIXTURES = _REPOSITORY_ROOT / "tests" / "fixtures"
_LONG_FIXTURE = _FIXTURES / "demo-long-conversations.json"
_MAX_FIXTURE_BYTES = 1_048_576


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
    load_fixture(settings, _FIXTURES / "sources.json")
    assert load_demo_conversations(settings, _LONG_FIXTURE) == 4
    return TestClient(create_app(settings=settings))


def _outline(
    client: TestClient, native_id: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    page = client.get("/api/v1/conversations").json()
    summary = next(item for item in page["items"] if item["native_id"] == native_id)
    detail = client.get(f"/api/v1/conversations/{summary['id']}").json()
    response = client.get(f"/api/v1/conversations/{summary['id']}/outline")
    assert response.status_code == 200, response.text
    return detail, response.json()


def _heading_count(outline: dict[str, Any]) -> int:
    return sum(len(event["headings"]) for event in outline["events"])


def test_fixture_stays_under_the_loader_limit() -> None:
    assert _LONG_FIXTURE.stat().st_size < _MAX_FIXTURE_BYTES


def test_library_holds_four_long_sessions(client: TestClient) -> None:
    page = client.get("/api/v1/conversations").json()
    assert page["total"] == 4
    by_native = {item["native_id"]: item for item in page["items"]}
    assert all(
        item["event_count"] >= 40
        for item in page["items"]
        if item["native_id"] != "demo-long-cli-review"
    )
    assert by_native["demo-long-cli-review"]["coverage"]["tool_calls"] == "partial"


def test_debugging_session_closes_with_citable_headings(client: TestClient) -> None:
    _, outline = _outline(client, "demo-long-ledger-debug")
    assert len(outline["paths"]) == 1
    (path,) = outline["paths"]
    assert len(path["segments"]) == 1
    assert _heading_count(outline) >= 5
    final_exchange = path["exchanges"][-1]
    assert final_exchange["heading_count"] >= 5
    assert any(e["tools"] for e in outline["events"] if e["role"] == "assistant")


def test_feature_session_splits_at_compaction_and_configuration(
    client: TestClient,
) -> None:
    _, outline = _outline(client, "demo-long-sitegen-incremental")
    (path,) = outline["paths"]
    assert len(path["segments"]) == 3
    assert [s["closed_by"] for s in path["segments"]] == [
        "compaction",
        "configuration",
        "end",
    ]
    assert _heading_count(outline) > 0


def test_branch_session_has_two_paths_and_a_failed_call(client: TestClient) -> None:
    detail, outline = _outline(client, "demo-long-sensor-backfill")
    assert len(outline["paths"]) == 2
    original = next(p for p in outline["paths"] if p["is_original"])
    alternate = next(p for p in outline["paths"] if not p["is_original"])
    assert original["fork_event_id"] == alternate["fork_event_id"]
    by_id = {event["id"]: event for event in detail["events"]}
    assert by_id[alternate["divergent_event_id"]]["native_id"] == "alt-a"
    assert len(original["event_ids"]) > len(alternate["event_ids"])
    results = [
        block["text"]
        for event in detail["events"]
        for block in event["content"]
        if block["kind"] == "tool_result" and block["text"]
    ]
    assert any(text.startswith("Error:") for text in results)


def test_review_session_is_prose_and_continues_the_debugging_session(
    client: TestClient,
) -> None:
    detail, outline = _outline(client, "demo-long-cli-review")
    assert _heading_count(outline) == 0
    assert outline["coverage"]["tool_calls"] == "partial"
    assistant_text = sum(
        e["text_chars"] for e in outline["events"] if e["role"] == "assistant"
    )
    assert assistant_text > 5000
    assert [r["kind"] for r in detail["relationships"]] == ["continuation"]
    target = detail["relationships"][0]
    assert target["target_native_id"] == "demo-long-ledger-debug"
    ledger_detail, _ = _outline(client, "demo-long-ledger-debug")
    assert [r["kind"] for r in ledger_detail["referenced_by"]] == ["continuation"]
