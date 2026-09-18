import datetime as dt
import os
from pathlib import Path
import subprocess

from sqlalchemy import select

from benchwarmer.config import BenchwarmerSettings
from benchwarmer.db import create_engine, create_session_factory
from benchwarmer.models.source import ConfiguredCoverage, Source
from benchwarmer.services.fixtures import load_fixture
from benchwarmer.services.source_status import COVERAGE_DIMENSIONS, list_source_status

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


def test_source_status_is_ordered_and_uses_only_successful_imports(
    tmp_path: Path,
) -> None:
    settings = _migrated_settings(tmp_path)
    load_fixture(settings, _FIXTURE)
    engine = create_engine(settings)
    factory = create_session_factory(engine)
    try:
        with factory() as session:
            statuses = list_source_status(session)
    finally:
        engine.dispose()

    assert [status.id for status in statuses] == [
        "fixture-source-codex-never-imported",
        "fixture-source-hermes-partial",
        "fixture-source-pi-failed",
    ]
    by_id = {status.id: status for status in statuses}
    assert by_id[
        "fixture-source-hermes-partial"
    ].last_successful_import_at == dt.datetime(2026, 9, 16, 11, 55, 2, tzinfo=dt.UTC)
    assert by_id["fixture-source-pi-failed"].last_successful_import_at is None
    assert (
        by_id["fixture-source-codex-never-imported"].last_successful_import_at is None
    )


def test_source_status_returns_every_dimension_without_inventing_missing_coverage(
    tmp_path: Path,
) -> None:
    settings = _migrated_settings(tmp_path)
    load_fixture(settings, _FIXTURE)
    engine = create_engine(settings)
    factory = create_session_factory(engine)
    try:
        with factory() as session:
            partial = session.scalar(
                select(Source).where(Source.id == "fixture-source-hermes-partial")
            )
            assert partial is not None
            partial.configured_coverage = ConfiguredCoverage(
                {"sessions": "available", "actual_charges": "unavailable"}
            )
            session.commit()
            statuses = list_source_status(session)
    finally:
        engine.dispose()

    by_id = {status.id: status for status in statuses}
    coverage = by_id["fixture-source-hermes-partial"].coverage
    assert tuple(coverage) == COVERAGE_DIMENSIONS
    assert coverage["sessions"] == "available"
    assert coverage["actual_charges"] == "unavailable"
    assert coverage["token_usage"] == "unknown"
    assert all(
        state == "unknown"
        for dimension, state in coverage.items()
        if dimension not in {"sessions", "actual_charges"}
    )
    assert by_id["fixture-source-codex-never-imported"].coverage == {
        dimension: "unknown" for dimension in COVERAGE_DIMENSIONS
    }
