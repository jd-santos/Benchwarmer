"""The models an operator can pick for app-started model work.

The harness owns provider knowledge: which providers have keys in the server's
environment, the pinned pi-ai catalog, models.dev, and each provider's own
model list. This service asks it (``npm run list-models -- --json``) and caches
the answer briefly so the Bundles page does not spawn a process per view.
Listing spends nothing and never reveals a key: the harness reports only the
variable names it reads.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import datetime as dt
import json
import os
import subprocess
import threading
from typing import Any

from benchwarmer.config import BenchwarmerSettings

CATALOG_TTL = dt.timedelta(minutes=10)
LIST_TIMEOUT_SECONDS = 90.0


class CatalogUnavailable(RuntimeError):
    """The harness could not list models for this application."""


@dataclass(frozen=True)
class CatalogSnapshot:
    catalog: dict[str, Any]
    fetched_at: dt.datetime


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


class ModelCatalogService:
    """Lists models through the configured harness, with a short in-process cache."""

    def __init__(
        self,
        settings: BenchwarmerSettings,
        *,
        run: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
        clock: Callable[[], dt.datetime] = _now,
        ttl: dt.timedelta = CATALOG_TTL,
    ) -> None:
        self._settings = settings
        self._run = run
        self._clock = clock
        self._ttl = ttl
        self._lock = threading.Lock()
        self._snapshot: CatalogSnapshot | None = None

    def command(self, *, offline: bool = False) -> list[str]:
        """The exact listing command, for logs and tests."""
        if self._settings.harness_dir is None:
            raise CatalogUnavailable(
                "this application cannot list models; set BENCHWARMER_HARNESS_DIR"
            )
        if not (self._settings.harness_dir / "package.json").is_file():
            raise CatalogUnavailable(
                "BENCHWARMER_HARNESS_DIR does not hold the harness package"
            )
        command = [
            "npm",
            "--prefix",
            str(self._settings.harness_dir),
            "run",
            "--silent",
            "list-models",
            "--",
            "--json",
        ]
        if offline:
            command.append("--offline")
        return command

    def get(self, *, refresh: bool = False) -> CatalogSnapshot:
        """The cached catalog when fresh, otherwise a new listing."""
        with self._lock:
            snapshot = self._snapshot
            if (
                snapshot is not None
                and not refresh
                and self._clock() - snapshot.fetched_at < self._ttl
            ):
                return snapshot
            fresh = CatalogSnapshot(self._list(), self._clock())
            self._snapshot = fresh
            return fresh

    def _list(self) -> dict[str, Any]:
        command = self.command()
        try:
            result = self._run(
                command,
                cwd=str(self._settings.harness_dir),
                env=dict(os.environ),
                capture_output=True,
                text=True,
                timeout=LIST_TIMEOUT_SECONDS,
                check=False,
            )
        except subprocess.TimeoutExpired:
            raise CatalogUnavailable(
                f"the harness did not list models within {LIST_TIMEOUT_SECONDS:.0f}s"
            ) from None
        except OSError as error:
            raise CatalogUnavailable(f"could not start the harness: {error}") from None
        if result.returncode != 0:
            detail = (result.stderr or "").strip().splitlines()
            raise CatalogUnavailable(
                "the harness could not list models"
                + (f": {detail[-1]}" if detail else f" (exit {result.returncode})")
            )
        try:
            catalog = json.loads(result.stdout)
        except json.JSONDecodeError:
            raise CatalogUnavailable(
                "the harness returned something other than a model catalog"
            ) from None
        if not isinstance(catalog, dict) or not isinstance(catalog.get("models"), list):
            raise CatalogUnavailable("the harness returned an unexpected catalog shape")
        return catalog
