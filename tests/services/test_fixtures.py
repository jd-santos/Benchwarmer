import json
import os
from pathlib import Path
import subprocess

import pytest
from sqlalchemy import func, select

from benchwarmer.config import BenchwarmerSettings
from benchwarmer.db import create_engine, create_session_factory
from benchwarmer.models.import_batch import ImportBatch
from benchwarmer.models.source import Source
from benchwarmer.services.fixtures import FixtureLoadError, load_fixture


_REPOSITORY_ROOT = Path(__file__).parents[2]
_FIXTURE = _REPOSITORY_ROOT / "tests/fixtures/sources.json"


def _migrated_settings(tmp_path: Path) -> BenchwarmerSettings:
    root = tmp_path / "private"
    environment = os.environ | {"BENCHWARMER_DATA_ROOT": str(root)}
    result = subprocess.run(
        ["uv", "run", "alembic", "upgrade", "head"],
        cwd=_REPOSITORY_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    return BenchwarmerSettings(data_root=root)


def test_fixture_loads_partial_failed_and_never_imported_sources(
    tmp_path: Path,
) -> None:
    settings = _migrated_settings(tmp_path)

    result = load_fixture(settings, _FIXTURE)

    assert result.sources_created == 3
    assert result.batches_created == 3
    assert result.sources_existing == 0
    assert result.batches_existing == 0

    engine = create_engine(settings)
    factory = create_session_factory(engine)
    try:
        with factory() as session:
            sources = session.scalars(select(Source).order_by(Source.id)).all()
            batches = session.scalars(
                select(ImportBatch).order_by(ImportBatch.id)
            ).all()
    finally:
        engine.dispose()

    assert [source.id for source in sources] == [
        "fixture-source-codex-never-imported",
        "fixture-source-hermes-partial",
        "fixture-source-pi-failed",
    ]
    assert [batch.outcome for batch in batches] == ["partial", "succeeded", "failed"]
    assert {batch.source_id for batch in batches} == {
        "fixture-source-hermes-partial",
        "fixture-source-pi-failed",
    }


def test_fixture_reload_is_an_idempotent_no_op(tmp_path: Path) -> None:
    settings = _migrated_settings(tmp_path)
    first = load_fixture(settings, _FIXTURE)
    second = load_fixture(settings, _FIXTURE)

    assert (first.sources_created, first.batches_created) == (3, 3)
    assert (second.sources_created, second.batches_created) == (0, 0)
    assert (second.sources_existing, second.batches_existing) == (3, 3)

    engine = create_engine(settings)
    factory = create_session_factory(engine)
    try:
        with factory() as session:
            assert session.scalar(select(func.count()).select_from(Source)) == 3
            assert session.scalar(select(func.count()).select_from(ImportBatch)) == 3
    finally:
        engine.dispose()


def test_fixture_keeps_economics_coverage_dimensions_distinct(
    tmp_path: Path,
) -> None:
    settings = _migrated_settings(tmp_path)
    load_fixture(settings, _FIXTURE)

    engine = create_engine(settings)
    factory = create_session_factory(engine)
    try:
        with factory() as session:
            source = session.get(Source, "fixture-source-hermes-partial")
            batch = session.get(ImportBatch, "fixture-batch-hermes-partial")
            assert source is not None
            assert source.configured_coverage is not None
            assert batch is not None
            assert batch.observed_coverage is not None
            assert source.configured_coverage.dimensions == {
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
            }
            assert batch.observed_coverage.dimensions["actual_charges"] == "unknown"
            assert (
                batch.observed_coverage.dimensions["list_price_estimates"]
                == "unavailable"
            )
    finally:
        engine.dispose()


def test_fixture_rejects_missing_source_atomically(
    tmp_path: Path,
) -> None:
    settings = _migrated_settings(tmp_path)
    document = json.loads(_FIXTURE.read_text())
    document["import_batches"][0]["source_id"] = "missing-source"
    invalid_fixture = tmp_path / "invalid.json"
    invalid_fixture.write_text(json.dumps(document))

    with pytest.raises(FixtureLoadError, match="fixture records could not be loaded"):
        load_fixture(settings, invalid_fixture)

    engine = create_engine(settings)
    factory = create_session_factory(engine)
    try:
        with factory() as session:
            assert session.scalar(select(func.count()).select_from(Source)) == 0
            assert session.scalar(select(func.count()).select_from(ImportBatch)) == 0
    finally:
        engine.dispose()


def test_fixture_rejects_conflicting_reload_without_rewriting_evidence(
    tmp_path: Path,
) -> None:
    settings = _migrated_settings(tmp_path)
    load_fixture(settings, _FIXTURE)
    document = json.loads(_FIXTURE.read_text())
    document["import_batches"][0]["error_summary"] = "Changed summary"
    conflict = tmp_path / "conflict.json"
    conflict.write_text(json.dumps(document))

    with pytest.raises(FixtureLoadError, match="conflicts with stored record"):
        load_fixture(settings, conflict)

    engine = create_engine(settings)
    factory = create_session_factory(engine)
    try:
        with factory() as session:
            batch = session.get(ImportBatch, "fixture-batch-hermes-partial")
            assert batch is not None
            assert batch.error_summary == "One synthetic record was unavailable"
    finally:
        engine.dispose()


def test_fixture_cli_loads_and_reloads_with_bounded_summary(tmp_path: Path) -> None:
    settings = _migrated_settings(tmp_path)
    environment = os.environ | {"BENCHWARMER_DATA_ROOT": str(settings.data_root)}
    command = [
        "uv",
        "run",
        "python",
        "-m",
        "benchwarmer.services.fixtures",
        "--load",
        str(_FIXTURE),
    ]

    first = subprocess.run(
        command,
        cwd=_REPOSITORY_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    second = subprocess.run(
        command,
        cwd=_REPOSITORY_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert first.returncode == 0, first.stderr
    assert first.stdout == "loaded sources=3 batches=3; existing sources=0 batches=0\n"
    assert second.returncode == 0, second.stderr
    assert second.stdout == "loaded sources=0 batches=0; existing sources=3 batches=3\n"
