import sqlite3
from pathlib import Path

import pytest

from benchwarmer.sqlite_runtime import (
    require_wal_safe_sqlite,
    sqlite_has_wal_reset_fix,
)


def test_project_runtime_is_wal_safe() -> None:
    require_wal_safe_sqlite()


@pytest.mark.parametrize(
    "version",
    [
        (3, 44, 5),
        (3, 45, 99),
        (3, 46, 99),
        (3, 47, 99),
        (3, 48, 99),
        (3, 49, 99),
        (3, 50, 4),
        (3, 50, 6),
        (3, 51, 2),
        (3, 51),
        (3, 51, 3, 0),
        (3, 51, "3"),
        (4, -1, 0),
    ],
)
def test_sqlite_without_wal_reset_fix_is_rejected(version: object) -> None:
    assert not sqlite_has_wal_reset_fix(version)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "version",
    [
        (3, 44, 6),
        (3, 44, 7),
        (3, 50, 7),
        (3, 50, 8),
        (3, 51, 3),
        (3, 51, 4),
        (3, 53, 4),
        (4, 0, 0),
    ],
)
def test_sqlite_with_wal_reset_fix_is_accepted(
    version: tuple[int, int, int],
) -> None:
    assert sqlite_has_wal_reset_fix(version)


def test_guard_reports_observed_version_and_accepted_thresholds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sqlite3, "sqlite_version_info", (3, 50, 4))
    monkeypatch.setattr(sqlite3, "sqlite_version", "3.50.4")

    with pytest.raises(RuntimeError) as error:
        require_wal_safe_sqlite()

    message = str(error.value)
    assert "3.50.4" in message
    assert "3.51.3+" in message
    assert "3.50.7+ on the 3.50 branch" in message
    assert "3.44.6+ on the 3.44 branch" in message


def test_guard_does_not_open_a_database(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sqlite3, "sqlite_version_info", (3, 53, 4))

    def fail_if_called(*args: object, **kwargs: object) -> None:
        pytest.fail("the SQLite runtime guard must not open a database")

    monkeypatch.setattr(sqlite3, "connect", fail_if_called)

    assert require_wal_safe_sqlite() is None


def test_rejected_runtime_prevents_database_io(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    database = tmp_path / "blocked.db"
    database_files = (
        database,
        database.with_name(f"{database.name}-wal"),
        database.with_name(f"{database.name}-shm"),
    )
    connect_called = False

    monkeypatch.setattr(sqlite3, "sqlite_version_info", (3, 50, 4))
    monkeypatch.setattr(sqlite3, "sqlite_version", "3.50.4")

    def fail_if_called(*args: object, **kwargs: object) -> None:
        nonlocal connect_called
        connect_called = True
        pytest.fail("a rejected SQLite runtime must not open a database")

    monkeypatch.setattr(sqlite3, "connect", fail_if_called)

    def future_entrypoint() -> None:
        require_wal_safe_sqlite()
        sqlite3.connect(database)

    with pytest.raises(RuntimeError, match="linked SQLite 3.50.4"):
        future_entrypoint()

    assert not connect_called
    assert all(not path.exists() for path in database_files)
