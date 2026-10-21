"""The outline route over the synthetic demo library."""

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
    load_demo_conversations(settings, _FIXTURES / "demo-conversations.json")
    return TestClient(create_app(settings=settings))


def _conversation(client: TestClient, native_id: str) -> dict[str, Any]:
    page = client.get("/api/v1/conversations").json()
    summary = next(item for item in page["items"] if item["native_id"] == native_id)
    return client.get(f"/api/v1/conversations/{summary['id']}").json()


def test_outline_matches_conversation_detail(client: TestClient) -> None:
    detail = _conversation(client, "demo-event-kinds")
    conversation_id = detail["summary"]["id"]

    response = client.get(f"/api/v1/conversations/{conversation_id}/outline")

    assert response.status_code == 200, response.text
    outline = response.json()
    assert outline["conversation_id"] == conversation_id
    assert outline["revision"] == detail["summary"]["revision"]
    assert outline["event_count"] == len(detail["events"])
    assert [e["id"] for e in outline["events"]] == [e["id"] for e in detail["events"]]
    assert [p["id"] for p in outline["paths"]] == [b["id"] for b in detail["branches"]]
    boundaries = {e["kind"] for e in outline["events"] if e["boundary"]}
    assert boundaries == {"compaction", "configuration"}
    assert any(e["headings"] for e in outline["events"])
    assert outline["producer"] == "benchwarmer.outline"

    pinned = client.get(
        f"/api/v1/conversations/{conversation_id}/outline",
        params={"revision": detail["summary"]["revision"]},
    )
    assert pinned.json() == outline


def test_outline_unknown_conversation_is_404(client: TestClient) -> None:
    assert client.get("/api/v1/conversations/missing/outline").status_code == 404
