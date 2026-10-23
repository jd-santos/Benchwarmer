"""Host-local file imports started from the web app."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess

from fastapi.testclient import TestClient

from benchwarmer.api.app import create_app
from benchwarmer.config import BenchwarmerSettings
from benchwarmer.services.fixtures import load_fixture

_REPOSITORY_ROOT = Path(__file__).parents[2]
_SOURCES = _REPOSITORY_ROOT / "tests/fixtures/sources.json"
_PI_SESSION = _REPOSITORY_ROOT / "tests/fixtures/pi-session-synthetic.jsonl"
_PI_SOURCE = "fixture-source-pi-failed"


def _client(tmp_path: Path, roots: tuple[Path, ...]) -> TestClient:
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
    settings = BenchwarmerSettings(data_root=root, import_roots=roots)
    load_fixture(settings, _SOURCES)
    return TestClient(create_app(settings=settings))


def test_import_config_names_roots_and_importable_kinds(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    client = _client(tmp_path, (inbox,))

    assert client.get("/api/v1/imports/config").json() == {
        "roots": [str(inbox)],
        "kinds": ["pi", "chatgpt"],
    }


def test_imports_a_pi_directory_under_a_root_once(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    sessions = inbox / "pi-sessions"
    sessions.mkdir(parents=True)
    shutil.copy(_PI_SESSION, sessions / "session.jsonl")
    client = _client(tmp_path, (inbox,))

    first = client.post(
        f"/api/v1/sources/{_PI_SOURCE}/imports", json={"path": str(sessions)}
    )
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["outcome"] == "succeeded"
    assert body["conversations"] == 1
    assert body["revisions"] == 1
    assert body["snapshots"] == 1
    assert body["error_summary"] is None

    # The same unchanged files import nothing new.
    again = client.post(
        f"/api/v1/sources/{_PI_SOURCE}/imports", json={"path": str(sessions)}
    ).json()
    assert again["outcome"] == "unchanged"
    assert again["batch_id"] == body["batch_id"]

    listed = client.get(f"/api/v1/sources/{_PI_SOURCE}/imports").json()["items"]
    outcomes = [item["outcome"] for item in listed]
    assert outcomes[0] == "succeeded"
    assert "failed" in outcomes  # the fixture's own earlier failed batch is kept

    titles = client.get("/api/v1/conversations").json()["items"]
    assert any(item["native_id"] == "synthetic-pi-anonymizer" for item in titles)


def test_rejects_paths_outside_roots_and_records_unreadable_ones(
    tmp_path: Path,
) -> None:
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    client = _client(tmp_path, (inbox,))

    outside = client.post(
        f"/api/v1/sources/{_PI_SOURCE}/imports", json={"path": str(elsewhere)}
    )
    assert outside.status_code == 422
    assert "outside" in outside.json()["detail"]

    relative = client.post(
        f"/api/v1/sources/{_PI_SOURCE}/imports", json={"path": "inbox"}
    )
    assert relative.status_code == 422

    missing = client.post(
        f"/api/v1/sources/{_PI_SOURCE}/imports", json={"path": str(inbox / "nope")}
    )
    assert missing.status_code == 422

    # An empty directory is readable but holds no sessions: a recorded failure.
    empty = inbox / "empty"
    empty.mkdir()
    failed = client.post(
        f"/api/v1/sources/{_PI_SOURCE}/imports", json={"path": str(empty)}
    ).json()
    assert failed["outcome"] == "failed"
    assert failed["error_summary"]
    listed = client.get(f"/api/v1/sources/{_PI_SOURCE}/imports").json()["items"]
    assert listed[0]["id"] == failed["batch_id"]
    assert listed[0]["outcome"] == "failed"

    collected = client.post(
        "/api/v1/sources/fixture-source-hermes-partial/imports",
        json={"path": str(inbox)},
    )
    assert collected.status_code == 422
    assert (
        client.post(
            "/api/v1/sources/nope/imports", json={"path": str(inbox)}
        ).status_code
        == 404
    )


def test_no_roots_means_no_host_import(tmp_path: Path) -> None:
    client = _client(tmp_path, ())
    response = client.post(
        f"/api/v1/sources/{_PI_SOURCE}/imports", json={"path": str(tmp_path)}
    )
    assert response.status_code == 422
    assert "BENCHWARMER_IMPORT_ROOTS" in response.json()["detail"]
