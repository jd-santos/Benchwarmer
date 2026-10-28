"""Plans for model work started from the application: preview, approve, run, cancel."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import time
from typing import Any

from fastapi.testclient import TestClient

from benchwarmer.api.app import create_app
from benchwarmer.config import BenchwarmerSettings
from benchwarmer.services.demo_conversations import load_demo_conversations
from benchwarmer.services.fixtures import load_fixture
from benchwarmer.services.model_work_plans import PlanRunner

_REPOSITORY_ROOT = Path(__file__).parents[2]
_FIXTURE = _REPOSITORY_ROOT / "tests" / "fixtures" / "demo-conversations.json"


def _fake_harness(path: Path, *, exit_code: int = 0, sleep: float = 0.0) -> Path:
    """A stand-in harness package: records its arguments and exits as told."""
    path.mkdir(parents=True)
    (path / "package.json").write_text(
        json.dumps(
            {
                "name": "fake-harness",
                "version": "0.0.0",
                "scripts": {
                    "propose-bundles": "node fake.js",
                    "list-models": "node list.js",
                },
            }
        )
    )
    record_env = (
        "fs.writeFileSync('env.json', JSON.stringify({"
        "allow: process.env.BENCHWARMER_PROVIDER_ALLOW, "
        "deny: process.env.BENCHWARMER_PROVIDER_DENY}));\n"
    )
    (path / "fake.js").write_text(
        "const fs = require('node:fs');\n"
        "fs.writeFileSync('args.json', JSON.stringify(process.argv.slice(2)));\n"
        + record_env
        + f"setTimeout(() => process.exit({exit_code}), {int(sleep * 1000)});\n"
    )
    (path / "list.js").write_text(
        "const fs = require('node:fs');\n"
        "fs.writeFileSync('list-args.json', JSON.stringify(process.argv.slice(2)));\n"
        + record_env
        + "process.stderr.write('models.dev unavailable: offline\\n');\n"
        f"process.stdout.write(JSON.stringify({json.dumps(_CATALOG)}) + '\\n');\n"
    )
    return path


_CATALOG: dict[str, Any] = {
    "generated_at": "2026-10-23T12:00:00.000Z",
    "providers": [
        {
            "id": "anthropic",
            "name": "Anthropic",
            "key_variables": ["ANTHROPIC_API_KEY"],
            "base_url_override": None,
            "provider_list": "listed",
            "models_dev": "unavailable",
            "model_count": 2,
        }
    ],
    "models": [
        {
            "provider": "anthropic",
            "id": "claude-sonnet-6",
            "name": "Claude Sonnet 6",
            "reasoning": None,
            "thinking_levels": ["low", "medium", "high", "xhigh", "max"],
            "context_window": None,
            "max_output": None,
            "release_date": "2027-01-15",
            "cost": None,
            "sources": ["provider"],
            "listed_by_provider": True,
            "runnable": True,
        },
        {
            "provider": "anthropic",
            "id": "claude-sonnet-5-5",
            "name": "Claude Sonnet 5.5",
            "reasoning": True,
            "thinking_levels": ["low", "medium", "high", "xhigh", "max"],
            "context_window": 1000000,
            "max_output": 128000,
            "release_date": "2026-09-01",
            "cost": {"input": 3, "output": 15, "cache_read": 0.3, "cache_write": 3.75},
            "sources": ["pi-ai", "provider"],
            "listed_by_provider": True,
            "runnable": True,
        },
    ],
    "notes": ["models.dev could not be read: offline"],
}


def _client(tmp_path: Path, harness: Path | None) -> tuple[TestClient, PlanRunner]:
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
    settings = BenchwarmerSettings(
        data_root=root,
        harness_dir=harness,
        provider_allow=("anthropic", "openrouter"),
        provider_deny=("openrouter",),
    )
    load_fixture(settings, _REPOSITORY_ROOT / "tests" / "fixtures" / "sources.json")
    load_demo_conversations(settings, _FIXTURE)
    runner = PlanRunner(settings)
    return TestClient(create_app(settings=settings, plan_runner=runner)), runner


def _conversation_ids(client: TestClient) -> list[str]:
    return [item["id"] for item in client.get("/api/v1/conversations").json()["items"]]


def _plan_request(ids: list[str], **extra: Any) -> dict[str, Any]:
    return {
        "workflow": "propose-bundles",
        "conversation_ids": ids,
        "model": {
            "provider": "anthropic",
            "model_id": "test-model",
            "thinking_level": "low",
        },
        **extra,
    }


def _wait_for(
    client: TestClient, plan_id: str, statuses: set[str], seconds: float = 10
) -> dict[str, Any]:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        plan = client.get(f"/api/v1/model-work/plans/{plan_id}").json()
        if plan["status"] in statuses:
            return plan
        time.sleep(0.1)
    raise AssertionError(f"plan {plan_id} did not reach {statuses}: {plan['status']}")


def test_config_says_whether_runs_can_start_here(tmp_path: Path) -> None:
    off, _ = _client(tmp_path / "off", None)
    assert off.get("/api/v1/model-work/config").json() == {
        "can_run": False,
        "workflows": ["propose-bundles"],
        "thinking_levels": ["off", "minimal", "low", "medium", "high", "xhigh", "max"],
        "max_inputs": 200,
    }
    on, _ = _client(tmp_path / "on", _fake_harness(tmp_path / "harness"))
    assert on.get("/api/v1/model-work/config").json()["can_run"] is True


def test_plan_freezes_inputs_and_only_its_digest_approves_it(tmp_path: Path) -> None:
    harness = _fake_harness(tmp_path / "harness")
    client, runner = _client(tmp_path, harness)
    ids = _conversation_ids(client)[:2]

    created = client.post(
        "/api/v1/model-work/plans", json=_plan_request(ids, instructions="  ")
    )
    assert created.status_code == 201, created.text
    plan = created.json()
    assert plan["status"] == "proposed"
    assert [item["conversation_id"] for item in plan["inputs"]] == ids
    assert all(item["revision"] for item in plan["inputs"])
    assert plan["max_inputs"] == 2
    assert plan["instructions"] is None
    assert plan["estimated_cost"] is None
    assert plan["run_id"] is None

    wrong = client.post(
        f"/api/v1/model-work/plans/{plan['id']}/approve", json={"digest": "0" * 64}
    )
    assert wrong.status_code == 409
    assert (
        client.get(f"/api/v1/model-work/plans/{plan['id']}").json()["status"]
        == "proposed"
    )

    approved = client.post(
        f"/api/v1/model-work/plans/{plan['id']}/approve",
        json={"digest": plan["digest"]},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] in {"running", "finished"}
    run_id = approved.json()["run_id"]
    assert run_id.startswith("propose-bundles-")

    finished = _wait_for(client, plan["id"], {"finished", "failed"})
    runner.wait_all(5)
    assert finished["status"] == "finished", finished
    assert finished["exit_code"] == 0
    args = json.loads((harness / "args.json").read_text())
    assert args[:2] == ["--api", "http://testserver"]
    assert (
        "--model" in args and args[args.index("--model") + 1] == "anthropic/test-model"
    )
    assert args[args.index("--run-id") + 1] == run_id
    assert args[args.index("--thinking") + 1] == "low"
    assert [args[i + 1] for i, a in enumerate(args) if a == "--conversation"] == ids
    # The provider lists reach the harness through its environment.
    assert json.loads((harness / "env.json").read_text()) == {
        "allow": "anthropic,openrouter",
        "deny": "openrouter",
    }
    log = Path(
        finished["id"]
        and (tmp_path / "private" / "logs" / "model-work" / f"{plan['id']}.log")
    )
    assert log.read_text().startswith("$ npm --prefix")

    # A second approval of the same plan is refused: it already ran.
    again = client.post(
        f"/api/v1/model-work/plans/{plan['id']}/approve",
        json={"digest": plan["digest"]},
    )
    assert again.status_code == 409
    assert [
        item["id"] for item in client.get("/api/v1/model-work/plans").json()["items"]
    ] == [plan["id"]]


def test_failed_and_cancelled_runs_are_recorded(tmp_path: Path) -> None:
    client, runner = _client(tmp_path, _fake_harness(tmp_path / "harness", exit_code=3))
    ids = _conversation_ids(client)[:1]
    plan = client.post("/api/v1/model-work/plans", json=_plan_request(ids)).json()
    client.post(
        f"/api/v1/model-work/plans/{plan['id']}/approve",
        json={"digest": plan["digest"]},
    )
    failed = _wait_for(client, plan["id"], {"failed", "finished"})
    runner.wait_all(5)
    assert failed["status"] == "failed"
    assert failed["exit_code"] == 3
    assert "status 3" in failed["error_summary"]

    slow_client, slow_runner = _client(
        tmp_path / "slow", _fake_harness(tmp_path / "slow-harness", sleep=30)
    )
    ids = _conversation_ids(slow_client)[:1]
    plan = slow_client.post("/api/v1/model-work/plans", json=_plan_request(ids)).json()
    started = slow_client.post(
        f"/api/v1/model-work/plans/{plan['id']}/approve",
        json={"digest": plan["digest"]},
    ).json()
    assert started["status"] == "running"
    cancelled = slow_client.post(f"/api/v1/model-work/plans/{plan['id']}/cancel").json()
    assert cancelled["status"] == "cancelled"
    slow_runner.wait_all(10)
    assert (
        slow_client.get(f"/api/v1/model-work/plans/{plan['id']}").json()["status"]
        == "cancelled"
    )
    assert (
        slow_client.post(f"/api/v1/model-work/plans/{plan['id']}/cancel").status_code
        == 409
    )


def test_plans_are_refused_when_they_cannot_run_or_name_bad_inputs(
    tmp_path: Path,
) -> None:
    client, _ = _client(tmp_path, None)
    ids = _conversation_ids(client)[:1]
    assert (
        client.post(
            "/api/v1/model-work/plans", json=_plan_request(["nope"])
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/v1/model-work/plans", json=_plan_request(ids, workflow="judge")
        ).status_code
        == 422
    )
    bad_model = _plan_request(ids)
    bad_model["model"]["thinking_level"] = "extreme"
    assert client.post("/api/v1/model-work/plans", json=bad_model).status_code == 422

    # Previewing works without a harness; approving does not.
    plan = client.post("/api/v1/model-work/plans", json=_plan_request(ids)).json()
    refused = client.post(
        f"/api/v1/model-work/plans/{plan['id']}/approve",
        json={"digest": plan["digest"]},
    )
    assert refused.status_code == 422
    assert "BENCHWARMER_HARNESS_DIR" in refused.json()["detail"]
    assert (
        client.get(f"/api/v1/model-work/plans/{plan['id']}").json()["status"]
        == "proposed"
    )
    assert client.get("/api/v1/model-work/plans/nope").status_code == 404


def test_startup_marks_plans_left_running_as_interrupted(tmp_path: Path) -> None:
    client, runner = _client(tmp_path, _fake_harness(tmp_path / "harness", sleep=30))
    ids = _conversation_ids(client)[:1]
    plan = client.post("/api/v1/model-work/plans", json=_plan_request(ids)).json()
    started = client.post(
        f"/api/v1/model-work/plans/{plan['id']}/approve",
        json={"digest": plan["digest"]},
    ).json()
    assert started["status"] == "running"

    # A new process over the same data root finds the plan still marked running.
    settings = BenchwarmerSettings(data_root=tmp_path / "private")
    with TestClient(create_app(settings=settings)) as restarted:
        recovered = restarted.get(f"/api/v1/model-work/plans/{plan['id']}").json()
    assert recovered["status"] == "interrupted"
    assert "stopped" in recovered["error_summary"]
    runner.terminate_all()
    runner.wait_all(10)


def test_lists_models_through_the_harness_without_revealing_keys(
    tmp_path: Path,
) -> None:
    harness = _fake_harness(tmp_path / "harness")
    client, _ = _client(tmp_path, harness)

    response = client.get("/api/v1/model-work/models")
    assert response.status_code == 200, response.text
    catalog = response.json()
    assert [model["id"] for model in catalog["models"]] == [
        "claude-sonnet-6",
        "claude-sonnet-5-5",
    ]
    assert catalog["providers"][0]["key_variables"] == ["ANTHROPIC_API_KEY"]
    assert catalog["notes"] == ["models.dev could not be read: offline"]
    assert catalog["fetched_at"]
    assert catalog["models"][1]["cost"]["input"] == 3.0
    assert json.loads((harness / "list-args.json").read_text()) == ["--json"]
    assert json.loads((harness / "env.json").read_text()) == {
        "allow": "anthropic,openrouter",
        "deny": "openrouter",
    }

    (harness / "list-args.json").unlink()
    assert client.get("/api/v1/model-work/models").status_code == 200
    assert not (harness / "list-args.json").exists(), "a fresh listing is cached"
    assert client.get("/api/v1/model-work/models?refresh=true").status_code == 200
    assert (harness / "list-args.json").exists()


def test_model_listing_is_unavailable_without_a_harness(tmp_path: Path) -> None:
    client, _ = _client(tmp_path, None)
    response = client.get("/api/v1/model-work/models")
    assert response.status_code == 503
    assert "BENCHWARMER_HARNESS_DIR" in response.json()["detail"]
