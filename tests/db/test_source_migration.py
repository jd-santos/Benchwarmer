import json
import os
from pathlib import Path
import subprocess

import pytest
from sqlalchemy import inspect
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import IntegrityError

from benchwarmer.config import BenchwarmerSettings
from benchwarmer.db import create_engine, current_revision


_REPOSITORY_ROOT = Path(__file__).parents[2]


def _run_alembic(root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ | {"BENCHWARMER_DATA_ROOT": str(root)}
    return subprocess.run(
        ["uv", "run", "alembic", *arguments],
        cwd=_REPOSITORY_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )


def _revision(root: Path) -> str | None:
    engine = create_engine(BenchwarmerSettings(data_root=root))
    try:
        return current_revision(engine)
    finally:
        engine.dispose()


def _insert_source(
    connection: Connection,
    *,
    source_id: str,
    kind: str,
    scope_id: str,
    display_name: str,
    configured_coverage: str | None = None,
) -> None:
    if configured_coverage is None:
        connection.exec_driver_sql(
            "INSERT INTO sources (id, kind, scope_id, display_name) "
            "VALUES (?, ?, ?, ?)",
            (source_id, kind, scope_id, display_name),
        )
        return
    connection.exec_driver_sql(
        "INSERT INTO sources "
        "(id, kind, scope_id, display_name, configured_coverage) "
        "VALUES (?, ?, ?, ?, ?)",
        (source_id, kind, scope_id, display_name, configured_coverage),
    )


def _assert_coverage_rejected(engine: Engine, coverage: str, index: int) -> None:
    with pytest.raises(IntegrityError, match="invalid configured coverage"):
        with engine.begin() as connection:
            _insert_source(
                connection,
                source_id=f"invalid-coverage-{index}",
                kind="coverage-validation",
                scope_id=f"invalid-scope-{index}",
                display_name="Invalid coverage",
                configured_coverage=coverage,
            )


def _assert_coverage_schema(engine: Engine) -> None:
    valid_coverage = json.dumps(
        {
            "schema_version": 1,
            "dimensions": {"adapter_specific_dimension": "partial"},
        }
    )
    with engine.begin() as connection:
        _insert_source(
            connection,
            source_id="source-with-coverage",
            kind="custom-adapter",
            scope_id="scope-with-coverage",
            display_name="Custom adapter",
            configured_coverage=valid_coverage,
        )

    invalid_coverages = (
        "{",
        json.dumps([]),
        json.dumps({"schema_version": 1}),
        json.dumps({"schema_version": 1, "dimensions": {}, "extra": True}),
        json.dumps({"schema_version": True, "dimensions": {}}),
        json.dumps({"schema_version": 1.0, "dimensions": {}}),
        json.dumps({"schema_version": 1, "dimensions": []}),
        json.dumps(
            {
                "schema_version": 1,
                "dimensions": {
                    f"dimension-{index}": "available" for index in range(65)
                },
            }
        ),
        json.dumps({"schema_version": 1, "dimensions": {"": "available"}}),
        json.dumps({"schema_version": 1, "dimensions": {"x" * 129: "available"}}),
        json.dumps({"schema_version": 1, "dimensions": {"sessions": "redacted"}}),
        json.dumps({"schema_version": 1, "dimensions": {"sessions": 1}}),
        '{"dimensions":{},"dimensions":{}}',
        '{"schema_version":1,"dimensions":{"sessions":"available","sessions":"unknown"}}',
    )
    for index, coverage in enumerate(invalid_coverages):
        _assert_coverage_rejected(engine, coverage, index)

    with pytest.raises(IntegrityError, match="invalid configured coverage"):
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "UPDATE sources SET configured_coverage = ? WHERE id = ?",
                (
                    '{"schema_version":1,"dimensions":{"sessions":"available","sessions":"unknown"}}',
                    "source-with-coverage",
                ),
            )


def _assert_sources_schema(root: Path) -> None:
    engine = create_engine(BenchwarmerSettings(data_root=root))
    try:
        inspector = inspect(engine)
        columns = {
            column["name"]: column for column in inspector.get_columns("sources")
        }
        constraints = inspector.get_unique_constraints("sources")
        primary_key = inspector.get_pk_constraint("sources")

        assert set(columns) == {
            "id",
            "kind",
            "scope_id",
            "display_name",
            "configured_coverage",
            "created_at",
            "updated_at",
        }
        assert all(
            columns[name]["nullable"] is False
            for name in (
                "id",
                "kind",
                "scope_id",
                "display_name",
                "created_at",
                "updated_at",
            )
        )
        assert columns["configured_coverage"]["nullable"] is True
        assert columns["created_at"]["default"] is not None
        assert columns["updated_at"]["default"] is not None
        assert primary_key["constrained_columns"] == ["id"]
        assert {tuple(item["column_names"]) for item in constraints} == {
            ("kind", "scope_id"),
        }

        with engine.begin() as connection:
            _insert_source(
                connection,
                source_id="source-one",
                kind="future-adapter",
                scope_id="scope-one",
                display_name="Future adapter",
            )
            row = connection.exec_driver_sql(
                "SELECT configured_coverage, created_at, updated_at FROM sources"
            ).one()
        assert row.configured_coverage is None
        assert row.created_at is not None
        assert row.updated_at is not None

        invalid_rows = (
            {
                "source_id": "source-one",
                "kind": "other-adapter",
                "scope_id": "other-scope",
                "display_name": "Duplicate primary key",
            },
            {
                "source_id": "source-two",
                "kind": "future-adapter",
                "scope_id": "scope-one",
                "display_name": "Duplicate source identity",
            },
            {
                "source_id": " ",
                "kind": "adapter",
                "scope_id": "scope-id",
                "display_name": "Blank primary key",
            },
            {
                "source_id": "blank-kind",
                "kind": " ",
                "scope_id": "scope-id",
                "display_name": "Blank kind",
            },
            {
                "source_id": "blank-scope",
                "kind": "adapter",
                "scope_id": " ",
                "display_name": "Blank scope",
            },
            {
                "source_id": "blank-display-name",
                "kind": "adapter",
                "scope_id": "scope-id",
                "display_name": " ",
            },
        )
        for values in invalid_rows:
            with pytest.raises(IntegrityError):
                with engine.begin() as connection:
                    _insert_source(connection, **values)

        _assert_coverage_schema(engine)
    finally:
        engine.dispose()


def test_sources_migration_round_trips_schema_and_revision(tmp_path: Path) -> None:
    root = tmp_path / "private"

    upgrade = _run_alembic(root, "upgrade", "0001")
    assert upgrade.returncode == 0, upgrade.stderr
    assert _revision(root) == "0001"
    _assert_sources_schema(root)

    downgrade = _run_alembic(root, "downgrade", "base")
    assert downgrade.returncode == 0, downgrade.stderr
    assert _revision(root) is None

    upgrade_again = _run_alembic(root, "upgrade", "0001")
    assert upgrade_again.returncode == 0, upgrade_again.stderr
    assert _revision(root) == "0001"
    _assert_sources_schema(root)
