import json
import os
from pathlib import Path
import subprocess

import pytest
from sqlalchemy import inspect
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


def _assert_import_batch_schema(root: Path) -> None:
    engine = create_engine(BenchwarmerSettings(data_root=root))
    try:
        inspector = inspect(engine)
        columns = {
            column["name"]: column for column in inspector.get_columns("import_batches")
        }
        assert set(columns) == {
            "id",
            "source_id",
            "idempotency_key",
            "outcome",
            "cursor_before",
            "cursor_after",
            "observed_coverage",
            "started_at",
            "completed_at",
            "error_summary",
        }
        assert columns["cursor_before"]["nullable"] is True
        assert columns["cursor_after"]["nullable"] is True
        assert columns["observed_coverage"]["nullable"] is True
        assert columns["error_summary"]["nullable"] is True
        assert columns["started_at"]["default"] is not None
        assert columns["completed_at"]["default"] is not None
        assert inspector.get_pk_constraint("import_batches")["constrained_columns"] == [
            "id"
        ]
        assert {
            tuple(item["column_names"])
            for item in inspector.get_unique_constraints("import_batches")
        } == {("source_id", "idempotency_key")}
        assert inspector.get_foreign_keys("import_batches")[0]["referred_table"] == (
            "sources"
        )

        with engine.begin() as connection:
            connection.exec_driver_sql(
                "INSERT OR IGNORE INTO sources (id, kind, scope_id, display_name) "
                "VALUES (?, ?, ?, ?)",
                ("source-one", "hermes", "scope-one", "Hermes"),
            )
            connection.exec_driver_sql(
                "INSERT INTO import_batches "
                "(id, source_id, idempotency_key, outcome, cursor_before, "
                "cursor_after, observed_coverage, error_summary) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    "batch-one",
                    "source-one",
                    "attempt-one",
                    "partial",
                    json.dumps({"schema_version": 1, "value": "message-1"}),
                    json.dumps(
                        {"schema_version": 1, "value": {"message_id": "message-2"}}
                    ),
                    json.dumps(
                        {
                            "schema_version": 1,
                            "dimensions": {"messages": "partial"},
                        }
                    ),
                    "one record could not be read",
                ),
            )
            row = connection.exec_driver_sql(
                "SELECT started_at, completed_at FROM import_batches"
            ).one()
        assert row.started_at is not None
        assert row.completed_at is not None

        invalid_statements = (
            (
                "INSERT INTO import_batches "
                "(id, source_id, idempotency_key, outcome) VALUES (?, ?, ?, ?)",
                ("orphan", "missing", "attempt", "succeeded"),
            ),
            (
                "INSERT INTO import_batches "
                "(id, source_id, idempotency_key, outcome) VALUES (?, ?, ?, ?)",
                ("invalid-outcome", "source-one", "attempt-two", "running"),
            ),
            (
                "INSERT INTO import_batches "
                "(id, source_id, idempotency_key, outcome) VALUES (?, ?, ?, ?)",
                ("failed-without-error", "source-one", "attempt-three", "failed"),
            ),
            (
                "INSERT INTO import_batches "
                "(id, source_id, idempotency_key, outcome, cursor_before) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    "bad-cursor",
                    "source-one",
                    "attempt-four",
                    "succeeded",
                    json.dumps({"schema_version": 2, "value": "message-1"}),
                ),
            ),
            (
                "INSERT INTO import_batches "
                "(id, source_id, idempotency_key, outcome, observed_coverage) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    "bad-coverage",
                    "source-one",
                    "attempt-five",
                    "succeeded",
                    json.dumps(
                        {
                            "schema_version": 1,
                            "dimensions": {"messages": "unsupported"},
                        }
                    ),
                ),
            ),
        )
        for statement, parameters in invalid_statements:
            with pytest.raises(IntegrityError):
                with engine.begin() as connection:
                    connection.exec_driver_sql(statement, parameters)

        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.exec_driver_sql(
                    "INSERT INTO import_batches "
                    "(id, source_id, idempotency_key, outcome) VALUES (?, ?, ?, ?)",
                    ("duplicate-request", "source-one", "attempt-one", "succeeded"),
                )
    finally:
        engine.dispose()


def _assert_hermes_schema(root: Path) -> None:
    engine = create_engine(BenchwarmerSettings(data_root=root))
    try:
        inspector = inspect(engine)
        expected_tables = {
            "native_snapshots",
            "native_sessions",
            "native_messages",
            "native_usages",
            "conversation_revisions",
            "source_presence",
            "source_import_states",
        }
        assert expected_tables <= set(inspector.get_table_names())
        assert inspector.get_pk_constraint("native_sessions")[
            "constrained_columns"
        ] == [
            "source_id",
            "native_id",
        ]
        assert inspector.get_pk_constraint("native_messages")[
            "constrained_columns"
        ] == [
            "source_id",
            "native_id",
        ]
        assert inspector.get_pk_constraint("source_import_states")[
            "constrained_columns"
        ] == ["source_id"]
        assert {
            tuple(item["column_names"])
            for item in inspector.get_unique_constraints("native_snapshots")
        } == {("source_id", "content_sha256")}
        assert {
            foreign_key["referred_table"]
            for table in expected_tables
            for foreign_key in inspector.get_foreign_keys(table)
        } >= {"sources", "import_batches"}
    finally:
        engine.dispose()


def test_import_batch_migration_round_trips_schema_and_revision(
    tmp_path: Path,
) -> None:
    root = tmp_path / "private"

    upgrade = _run_alembic(root, "upgrade", "head")
    assert upgrade.returncode == 0, upgrade.stderr
    assert _revision(root) == "0003"
    _assert_import_batch_schema(root)
    _assert_hermes_schema(root)

    downgrade = _run_alembic(root, "downgrade", "0001")
    assert downgrade.returncode == 0, downgrade.stderr
    assert _revision(root) == "0001"
    engine = create_engine(BenchwarmerSettings(data_root=root))
    try:
        tables = set(inspect(engine).get_table_names())
        assert "import_batches" not in tables
        assert (
            not {
                "native_snapshots",
                "native_sessions",
                "native_messages",
                "native_usages",
                "conversation_revisions",
                "source_presence",
                "source_import_states",
            }
            & tables
        )
        assert "sources" in tables
    finally:
        engine.dispose()

    upgrade_again = _run_alembic(root, "upgrade", "head")
    assert upgrade_again.returncode == 0, upgrade_again.stderr
    assert _revision(root) == "0003"
    _assert_import_batch_schema(root)
    _assert_hermes_schema(root)
