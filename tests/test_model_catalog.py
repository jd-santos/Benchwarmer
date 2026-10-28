"""Listing models through the harness: command, cache, and failure modes."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
import subprocess
from typing import Any

import pytest

from benchwarmer.config import BenchwarmerSettings
from benchwarmer.services.model_catalog import (
    CatalogUnavailable,
    ModelCatalogService,
)

CATALOG: dict[str, Any] = {
    "generated_at": "2026-10-23T12:00:00.000Z",
    "providers": [
        {
            "id": "anthropic",
            "name": "Anthropic",
            "key_variables": ["ANTHROPIC_API_KEY"],
            "base_url_override": None,
            "provider_list": "listed",
            "models_dev": "listed",
            "model_count": 1,
        }
    ],
    "models": [
        {
            "provider": "anthropic",
            "id": "claude-sonnet-5-5",
            "name": "Claude Sonnet 5.5",
            "reasoning": True,
            "thinking_levels": ["low", "medium", "high"],
            "context_window": 1000000,
            "max_output": 128000,
            "release_date": "2026-09-01",
            "cost": {"input": 3, "output": 15, "cache_read": 0.3, "cache_write": 3.75},
            "sources": ["pi-ai", "models.dev", "provider"],
            "listed_by_provider": True,
            "runnable": True,
        }
    ],
    "notes": [],
}


def _harness(tmp_path: Path) -> Path:
    harness = tmp_path / "harness"
    harness.mkdir()
    (harness / "package.json").write_text("{}")
    return harness


class _Clock:
    def __init__(self) -> None:
        self.now = dt.datetime(2026, 10, 23, 12, 0, tzinfo=dt.UTC)

    def __call__(self) -> dt.datetime:
        return self.now


class _Runner:
    """Stands in for subprocess.run; records calls and answers as told."""

    def __init__(self, stdout: str = "", returncode: int = 0, stderr: str = "") -> None:
        self.calls: list[list[str]] = []
        self.environments: list[dict[str, str]] = []
        self.stdout = stdout
        self.returncode = returncode
        self.stderr = stderr

    def __call__(
        self, command: list[str], **kwargs: Any
    ) -> subprocess.CompletedProcess[str]:
        self.calls.append(command)
        self.environments.append(dict(kwargs.get("env", {})))
        return subprocess.CompletedProcess(
            command, self.returncode, stdout=self.stdout, stderr=self.stderr
        )


def test_lists_through_the_harness_and_caches_until_the_ttl_or_a_refresh(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)
    runner = _Runner(stdout=json.dumps(CATALOG) + "\n")
    clock = _Clock()
    service = ModelCatalogService(
        BenchwarmerSettings(
            data_root=tmp_path / "data",
            harness_dir=harness,
            provider_allow=("anthropic", "google"),
        ),
        run=runner,
        clock=clock,
        ttl=dt.timedelta(minutes=10),
    )

    first = service.get()
    assert first.catalog["models"][0]["id"] == "claude-sonnet-5-5"
    assert first.fetched_at == clock.now
    # The settings' provider lists travel to the harness in its environment,
    # both always set so nothing is inherited from the shell.
    assert runner.environments[0]["BENCHWARMER_PROVIDER_ALLOW"] == "anthropic,google"
    assert runner.environments[0]["BENCHWARMER_PROVIDER_DENY"] == ""
    assert runner.calls == [
        [
            "npm",
            "--prefix",
            str(harness),
            "run",
            "--silent",
            "list-models",
            "--",
            "--json",
        ]
    ]

    clock.now += dt.timedelta(minutes=9)
    assert service.get() is first
    assert len(runner.calls) == 1

    assert service.get(refresh=True) is not first
    assert len(runner.calls) == 2

    clock.now += dt.timedelta(minutes=11)
    service.get()
    assert len(runner.calls) == 3


def test_refuses_without_a_harness_and_reports_a_failing_listing(
    tmp_path: Path,
) -> None:
    runner = _Runner(stdout=json.dumps(CATALOG))
    without = ModelCatalogService(
        BenchwarmerSettings(data_root=tmp_path / "data"), run=runner
    )
    with pytest.raises(CatalogUnavailable, match="BENCHWARMER_HARNESS_DIR"):
        without.get()
    assert runner.calls == []

    empty_dir = tmp_path / "not-a-harness"
    empty_dir.mkdir()
    with pytest.raises(CatalogUnavailable, match="does not hold the harness"):
        ModelCatalogService(
            BenchwarmerSettings(data_root=tmp_path / "data", harness_dir=empty_dir),
            run=runner,
        ).get()

    harness = _harness(tmp_path)
    settings = BenchwarmerSettings(data_root=tmp_path / "data", harness_dir=harness)
    failing = ModelCatalogService(
        settings, run=_Runner(returncode=1, stderr="x\nError: models.dev is down\n")
    )
    with pytest.raises(CatalogUnavailable, match="models.dev is down"):
        failing.get()

    garbage = ModelCatalogService(settings, run=_Runner(stdout="> banner\n{}"))
    with pytest.raises(CatalogUnavailable, match="something other than"):
        garbage.get()

    shapeless = ModelCatalogService(settings, run=_Runner(stdout='{"providers": []}'))
    with pytest.raises(CatalogUnavailable, match="unexpected catalog shape"):
        shapeless.get()

    def timeout(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    with pytest.raises(CatalogUnavailable, match="did not list models within"):
        ModelCatalogService(settings, run=timeout).get()
