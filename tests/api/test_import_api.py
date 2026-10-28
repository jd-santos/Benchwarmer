"""Host-local file imports started from the web app."""

from __future__ import annotations

import json
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

    config = client.get("/api/v1/imports/config").json()
    assert config["roots"] == [str(inbox)]
    assert config["kinds"] == ["pi", "chatgpt", "conversation_file"]
    assert [(i["kind"], i["accepts"]) for i in config["importers"]] == [
        ("pi", "file_or_directory"),
        ("chatgpt", "file"),
        ("conversation_file", "file_or_directory"),
    ]


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


_CONVERSATION_FILES = _REPOSITORY_ROOT / "tests/fixtures/conversation-files/valid"


def test_uploads_a_conversation_file_once_and_revises_it_when_it_changes(
    tmp_path: Path,
) -> None:
    client = _client(tmp_path, ())
    document = json.loads((_CONVERSATION_FILES / "agent-product-log.json").read_text())

    first = client.post("/api/v1/imports/conversation-files", json=document)
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["outcome"] == "succeeded" and body["new_revision"]
    assert body["native_id"] == "synthetic-conv-0001"
    assert body["conversation_id"].startswith("conversation-")
    assert body["revision"] and body["staged_path"].startswith("imports/staging/")
    assert (tmp_path / "private" / body["staged_path"]).is_file()

    # The scope became a source of its own.
    sources = client.get("/api/v1/sources").json()["items"]
    source = next(item for item in sources if item["id"] == body["source_id"])
    assert source["kind"] == "conversation_file"
    assert "synthetic-tenant-a" in source["display_name"]
    assert source["last_successful_import_at"] is not None

    again = client.post("/api/v1/imports/conversation-files", json=document).json()
    assert again["outcome"] == "unchanged"
    assert again["batch_id"] == body["batch_id"]
    assert again["revision"] == body["revision"] and not again["new_revision"]

    document["events"][-1]["content"][0]["text"] = "Renamed; the suite passes (13)."
    changed = client.post("/api/v1/imports/conversation-files", json=document).json()
    assert changed["outcome"] == "succeeded" and changed["new_revision"]
    assert changed["conversation_id"] == body["conversation_id"]
    assert changed["revision"] != body["revision"]

    detail = client.get(f"/api/v1/conversations/{body['conversation_id']}").json()
    assert detail["summary"]["revision"] == changed["revision"]
    assert any(event["kind"] == "configuration" for event in detail["events"])

    history = client.get(f"/api/v1/sources/{body['source_id']}/imports").json()
    assert [item["outcome"] for item in history["items"]] == ["succeeded", "succeeded"]


def test_upload_rejects_invalid_files_with_paths_and_checks_the_source(
    tmp_path: Path,
) -> None:
    client = _client(tmp_path, ())
    invalid = client.post(
        "/api/v1/imports/conversation-files",
        json={"format": "benchwarmer-conversation-file", "events": []},
    )
    assert invalid.status_code == 422
    paths = {issue["path"] for issue in invalid.json()["issues"]}
    assert {"$.format_version", "$.scope_id", "$.native_id", "$.events"} <= paths

    document = json.loads((_CONVERSATION_FILES / "minimal.json").read_text())
    wrong_kind = client.post(
        "/api/v1/imports/conversation-files",
        params={"source_id": _PI_SOURCE},
        json=document,
    )
    assert wrong_kind.status_code == 422
    assert "conversation_file" in wrong_kind.json()["detail"]
    assert (
        client.post(
            "/api/v1/imports/conversation-files",
            params={"source_id": "nope"},
            json=document,
        ).status_code
        == 404
    )
    created = client.post("/api/v1/imports/conversation-files", json=document).json()
    other = dict(document, scope_id="someone-else")
    mismatch = client.post(
        "/api/v1/imports/conversation-files",
        params={"source_id": created["source_id"]},
        json=other,
    )
    assert mismatch.status_code == 422 and "scope_id" in mismatch.json()["detail"]
    explicit = client.post(
        "/api/v1/imports/conversation-files",
        params={"source_id": created["source_id"]},
        json=document,
    ).json()
    assert explicit["outcome"] == "unchanged"


def test_imports_conversation_files_from_a_directory_under_a_root(
    tmp_path: Path,
) -> None:
    inbox = tmp_path / "inbox"
    folder = inbox / "files"
    folder.mkdir(parents=True)
    shutil.copy(_CONVERSATION_FILES / "minimal.json", folder / "one.json")
    shutil.copy(_CONVERSATION_FILES / "branches-and-gaps.json", folder / "two.json")
    client = _client(tmp_path, (inbox,))
    # Uploading one file creates the scope's source; the directory imports into it.
    minimal = json.loads((_CONVERSATION_FILES / "minimal.json").read_text())
    uploaded = client.post("/api/v1/imports/conversation-files", json=minimal).json()
    source_id = uploaded["source_id"]

    run = client.post(
        f"/api/v1/sources/{source_id}/imports", json={"path": str(folder)}
    )
    assert run.status_code == 200, run.text
    assert run.json()["outcome"] == "succeeded"
    assert run.json()["conversations"] == 2
    assert run.json()["revisions"] == 1  # minimal.json was already there

    # A kind that imports a single file refuses a directory before reading it.
    archive = inbox / "chat"
    archive.mkdir()
    refused = client.post(
        f"/api/v1/sources/{_PI_SOURCE}/imports", json={"path": str(archive)}
    )
    assert refused.json()["outcome"] == "failed"  # pi reads it and finds nothing
