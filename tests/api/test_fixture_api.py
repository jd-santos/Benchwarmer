"""Scrub and check routes over the synthetic Pi session; nothing is stored."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
from typing import Any

from fastapi.testclient import TestClient
import pytest

from benchwarmer.api.app import create_app
from benchwarmer.config import BenchwarmerSettings

_REPOSITORY_ROOT = Path(__file__).parents[2]
_SESSION = _REPOSITORY_ROOT / "tests" / "fixtures" / "pi-session-synthetic.jsonl"
_TERMS = ["Dana", "widget"]


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
    return TestClient(create_app(settings=BenchwarmerSettings(data_root=root)))


def _content() -> str:
    return _SESSION.read_text(encoding="utf-8")


def _scrub(client: TestClient) -> dict[str, Any]:
    response = client.post(
        "/api/v1/fixtures/scrub-pi-session",
        json={"content": _content(), "terms": _TERMS},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_scrub_returns_placeholders_and_a_report_without_originals(
    client: TestClient,
) -> None:
    body = _scrub(client)

    assert body["native_id"] == "synthetic-pi-anonymizer"
    assert body["source_version"] == "session-v3"
    assert body["report"]["producer"] == "benchwarmer.anonymize"
    assert body["report"]["counts"]["email"] == 1
    text = json.dumps(body)
    for private in ("example-corp", "/Users/dana", "10.20.30.40", "sk-synthetic"):
        assert private not in text
    assert "<email-1>" in text and "<url-1>" in text
    user = next(e for e in body["events"] if e["native_id"] == "u0")
    assert user["content"][0]["text"].startswith("hey so the nightly sync at <url-1>")
    assert body["fixture"]["events"][1]["parent_id"] == "c0"
    assert "id" not in body["fixture"]["events"][0]
    assert client.get("/api/v1/conversations").json()["total"] == 0


def test_check_passes_for_the_scrubbed_fixture_and_flags_drift_and_leaks(
    client: TestClient,
) -> None:
    body = _scrub(client)
    candidate = body["fixture"]

    passing = client.post(
        "/api/v1/fixtures/check",
        json={"content": _content(), "candidate": candidate, "terms": _TERMS},
    )
    assert passing.status_code == 200, passing.text
    assert passing.json() == {
        "schema_version": 1,
        "producer": "benchwarmer.anonymize",
        "producer_version": "1",
        "native_id": "synthetic-pi-anonymizer",
        "fidelity": [],
        "leaks": [],
        "ok": True,
    }

    broken = json.loads(json.dumps(candidate))
    broken["events"].pop()
    broken["events"][1]["content"][0]["text"] = (
        "ask dana at dana.example@example-corp.com"
    )
    failing = client.post(
        "/api/v1/fixtures/check",
        json={"content": _content(), "candidate": broken, "terms": _TERMS},
    ).json()
    assert failing["ok"] is False
    assert [i["code"] for i in failing["fidelity"]] == ["event_count"]
    assert [(i["code"], i["category"]) for i in failing["leaks"]] == [
        ("term", "term"),
        ("term", "term"),
        ("original_span", "email"),
    ]
    assert "example-corp" not in json.dumps(failing)


def test_malformed_session_content_is_422(client: TestClient) -> None:
    response = client.post(
        "/api/v1/fixtures/scrub-pi-session", json={"content": "not json\n"}
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "Pi session JSONL is invalid"
