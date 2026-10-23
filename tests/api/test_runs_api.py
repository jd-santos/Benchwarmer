"""Records of hand-run harness workflows and their estimated usage."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
from typing import Any

from fastapi.testclient import TestClient
import pytest

from benchwarmer.api.app import create_app
from benchwarmer.config import BenchwarmerSettings

_REPOSITORY_ROOT = Path(__file__).parents[2]


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


def _usage(output: int, cache_write: int, cost: float) -> dict[str, Any]:
    return {
        "models": {
            "anthropic/test-model": {
                "input": 10,
                "output": output,
                "cache_read": 0,
                "cache_write": cache_write,
                "total_tokens": 10 + output + cache_write,
                "cost": {
                    "input": 0.0,
                    "output": cost,
                    "cache_read": 0.0,
                    "cache_write": 0.0,
                    "total": cost,
                },
            }
        },
        "tools": {},
    }


def _record(run_id: str) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "workflow": "propose-bundles",
        "harness_version": "0.0.1",
        "started_at": "2026-10-22T23:16:02.479Z",
        "finished_at": "2026-10-22T23:16:31.173Z",
        "api_base_url": "http://127.0.0.1:8000",
        "model": {
            "provider": "anthropic",
            "model_id": "test-model",
            "thinking_level": None,
            "base_url_override": "https://gateway.example",
        },
        "producer": "benchwarmer-harness/propose-bundles@0.0.1 anthropic/test-model",
        "inputs": [
            {
                "id": "conversation-a",
                "kind": "conversation",
                "status": "done",
                "reason": None,
                "bundle_ids": ["bundle-1", "bundle-2"],
                "usage": _usage(3000, 20000, 0.10),
            },
            {
                "id": "conversation-b",
                "kind": "conversation",
                "status": "error",
                "reason": "timed out",
                "bundle_ids": [],
                "usage": _usage(0, 0, 0.0),
            },
        ],
        "usage_total": _usage(3000, 20000, 0.10),
        "pricing_source": "pi-ai model catalog estimate",
        "report_path": "reports/harness/run.json",
    }


def test_records_runs_idempotently_and_summarizes_usage(client: TestClient) -> None:
    run_id = "propose-bundles-2026-10-22T23-16-02-479Z"
    stored = client.put(f"/api/v1/runs/{run_id}", json=_record(run_id))
    assert stored.status_code == 200, stored.text
    assert stored.json() == _record(run_id)
    assert client.get(f"/api/v1/runs/{run_id}").json() == _record(run_id)

    listed = client.get("/api/v1/runs").json()["items"]
    assert len(listed) == 1
    summary = listed[0]
    assert summary["run_id"] == run_id
    assert summary["model"] == "test-model"
    assert summary["base_url_override"] == "https://gateway.example"
    assert summary["input_count"] == 2
    assert summary["bundle_count"] == 2
    assert summary["total_tokens"] == 23010
    assert summary["estimated_cost"] == pytest.approx(0.10)
    assert summary["pricing_source"] == "pi-ai model catalog estimate"

    # A later record of the same run replaces the first instead of duplicating it.
    later = dict(_record(run_id), usage_total=_usage(4000, 20000, 0.12))
    assert client.put(f"/api/v1/runs/{run_id}", json=later).status_code == 200
    listed = client.get("/api/v1/runs").json()["items"]
    assert [item["total_tokens"] for item in listed] == [24010]
    assert client.get("/api/v1/runs", params={"workflow": "other"}).json() == {
        "items": []
    }


def test_rejects_mismatched_or_malformed_records(client: TestClient) -> None:
    record = _record("run-1")
    assert client.put("/api/v1/runs/run-2", json=record).status_code == 422
    assert client.get("/api/v1/runs/run-1").status_code == 404
    malformed = dict(record, usage_total={"models": {"m": {"input": "ten"}}})
    assert client.put("/api/v1/runs/run-1", json=malformed).status_code == 422
    bad_time = dict(record, started_at="yesterday")
    assert client.put("/api/v1/runs/run-1", json=bad_time).status_code == 422
