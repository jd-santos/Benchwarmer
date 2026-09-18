import os
from pathlib import Path
import subprocess

from fastapi.testclient import TestClient

from benchwarmer.api.app import create_app
from benchwarmer.config import BenchwarmerSettings
from benchwarmer.services.fixtures import load_fixture

_REPOSITORY_ROOT = Path(__file__).parents[2]
_FIXTURE = _REPOSITORY_ROOT / "tests/fixtures/sources.json"


def _migrated_settings(tmp_path: Path) -> BenchwarmerSettings:
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
    return BenchwarmerSettings(data_root=root)


def test_sources_returns_a_stable_empty_envelope(tmp_path: Path) -> None:
    settings = _migrated_settings(tmp_path)
    client = TestClient(create_app(settings))

    response = client.get("/api/v1/sources")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.json() == {"items": []}


def test_sources_reads_fixture_records_and_preserves_coverage(tmp_path: Path) -> None:
    settings = _migrated_settings(tmp_path)
    load_fixture(settings, _FIXTURE)
    client = TestClient(create_app(settings))

    response = client.get("/api/v1/sources")

    assert response.status_code == 200
    body = response.json()
    assert [item["id"] for item in body["items"]] == [
        "fixture-source-codex-never-imported",
        "fixture-source-hermes-partial",
        "fixture-source-pi-failed",
    ]
    by_id = {item["id"]: item for item in body["items"]}
    assert by_id["fixture-source-hermes-partial"] == {
        "id": "fixture-source-hermes-partial",
        "kind": "hermes",
        "display_name": "Synthetic Hermes profile",
        "last_successful_import_at": "2026-09-16T11:55:02Z",
        "coverage": {
            "sessions": "available",
            "token_usage": "partial",
            "request_ids": "unavailable",
            "actual_charges": "unknown",
            "list_price_estimates": "unavailable",
            "subscription_expense": "unknown",
            "quota": "unknown",
            "credits": "unknown",
            "prompts": "partial",
            "classifications": "unknown",
        },
    }
    assert by_id["fixture-source-codex-never-imported"]["coverage"] == {
        "sessions": "unknown",
        "token_usage": "unknown",
        "request_ids": "unknown",
        "actual_charges": "unknown",
        "list_price_estimates": "unknown",
        "subscription_expense": "unknown",
        "quota": "unknown",
        "credits": "unknown",
        "prompts": "unknown",
        "classifications": "unknown",
    }


def test_sources_only_accepts_get(tmp_path: Path) -> None:
    client = TestClient(create_app(_migrated_settings(tmp_path)))

    assert client.post("/api/v1/sources").status_code == 405
