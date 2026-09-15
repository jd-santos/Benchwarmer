import os
from pathlib import Path
import stat
import subprocess
import sys

import pytest

from benchwarmer.config import BenchwarmerSettings, ConfigurationError
from benchwarmer.db import (
    create_engine,
    create_session_factory,
    current_revision,
    database_url,
)


_REPOSITORY_ROOT = Path(__file__).parents[2]


def _command_environment(root: Path) -> dict[str, str]:
    environment = os.environ.copy()
    environment["BENCHWARMER_DATA_ROOT"] = str(root)
    return environment


def _run_alembic(root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["uv", "run", "alembic", *arguments],
        cwd=_REPOSITORY_ROOT,
        env=_command_environment(root),
        check=False,
        capture_output=True,
        text=True,
    )


def _current_revision(settings: BenchwarmerSettings) -> str | None:
    engine = create_engine(settings)
    try:
        return current_revision(engine)
    finally:
        engine.dispose()


def test_database_url_preserves_the_configured_private_database_path(
    tmp_path: Path,
) -> None:
    settings = BenchwarmerSettings(data_root=tmp_path / "private?root")

    url = database_url(settings)

    assert url.drivername == "sqlite+pysqlite"
    assert url.database == str(settings.database_path)


def test_database_path_with_question_mark_connects_without_a_truncated_sibling(
    tmp_path: Path,
) -> None:
    settings = BenchwarmerSettings(data_root=tmp_path / "private?root")
    truncated_database = tmp_path / "private"
    engine = create_engine(settings)

    try:
        with engine.connect() as connection:
            connected_database = str(
                connection.exec_driver_sql("PRAGMA database_list").one()[2]
            )
    finally:
        engine.dispose()

    assert Path(connected_database) == settings.database_path
    assert settings.database_path.is_file()
    assert not truncated_database.exists()


def test_empty_migration_commands_leave_revision_absent(tmp_path: Path) -> None:
    root = tmp_path / "private"

    current = _run_alembic(root, "current")
    assert current.returncode == 0, current.stderr
    assert _current_revision(BenchwarmerSettings(data_root=root)) is None

    upgrade = _run_alembic(root, "upgrade", "head")
    assert upgrade.returncode == 0, upgrade.stderr
    assert _current_revision(BenchwarmerSettings(data_root=root)) is None

    downgrade = _run_alembic(root, "downgrade", "base")
    assert downgrade.returncode == 0, downgrade.stderr
    assert _current_revision(BenchwarmerSettings(data_root=root)) is None


def test_alembic_config_works_outside_the_repository(tmp_path: Path) -> None:
    root = tmp_path / "private"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "alembic",
            "-c",
            str(_REPOSITORY_ROOT / "alembic.ini"),
            "current",
        ],
        cwd=tmp_path,
        env=_command_environment(root),
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_offline_alembic_sql_does_not_create_the_configured_root(
    tmp_path: Path,
) -> None:
    root = tmp_path / "private"

    result = _run_alembic(root, "upgrade", "head", "--sql")

    assert result.returncode == 0, result.stderr
    assert not root.exists()


def test_current_revision_initializes_an_empty_database(tmp_path: Path) -> None:
    settings = BenchwarmerSettings(data_root=tmp_path / "private")

    assert _current_revision(settings) is None
    assert settings.database_path.is_file()
    assert stat.S_IMODE(settings.database_path.stat().st_mode) == 0o600


def test_existing_database_file_is_restricted_to_the_owner(tmp_path: Path) -> None:
    settings = BenchwarmerSettings(data_root=tmp_path / "private")
    settings.initialize()
    settings.database_path.write_bytes(b"")
    settings.database_path.chmod(0o644)

    assert _current_revision(settings) is None
    assert stat.S_IMODE(settings.database_path.stat().st_mode) == 0o600


def test_session_factory_uses_a_caller_owned_engine(tmp_path: Path) -> None:
    engine = create_engine(BenchwarmerSettings(data_root=tmp_path / "private"))

    try:
        factory = create_session_factory(engine)
        with factory() as session:
            assert session.bind is engine
    finally:
        engine.dispose()


def test_rejected_runtime_prevents_initialization_and_engine_work(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    settings = BenchwarmerSettings(data_root=tmp_path / "private")
    calls: list[str] = []

    def reject_runtime() -> None:
        calls.append("guard")
        raise RuntimeError("WAL safety gate blocked")

    def fail_if_called(*args: object, **kwargs: object) -> None:
        del args, kwargs
        pytest.fail("database work must not follow a rejected runtime gate")

    monkeypatch.setattr("benchwarmer.db.require_wal_safe_sqlite", reject_runtime)
    monkeypatch.setattr(BenchwarmerSettings, "initialize", fail_if_called)
    monkeypatch.setattr("benchwarmer.db._secure_database_file", fail_if_called)
    monkeypatch.setattr("benchwarmer.db.sqlalchemy_create_engine", fail_if_called)

    with pytest.raises(RuntimeError, match="WAL safety gate blocked"):
        create_engine(settings)

    assert calls == ["guard"]
    assert not settings.data_root.exists()


def test_runtime_gate_runs_again_before_each_dbapi_connection(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    settings = BenchwarmerSettings(data_root=tmp_path / "private")
    calls = 0

    def guard() -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("WAL safety gate blocked")

    monkeypatch.setattr("benchwarmer.db.require_wal_safe_sqlite", guard)
    engine = create_engine(settings)

    try:
        with pytest.raises(RuntimeError, match="WAL safety gate blocked"):
            engine.connect()
    finally:
        engine.dispose()

    assert calls == 2
    assert settings.database_path.read_bytes() == b""
    assert not settings.database_path.with_name(
        f"{settings.database_path.name}-wal"
    ).exists()
    assert not settings.database_path.with_name(
        f"{settings.database_path.name}-shm"
    ).exists()


def test_default_journal_mode_is_delete_without_wal_sidecars(tmp_path: Path) -> None:
    settings = BenchwarmerSettings(data_root=tmp_path / "private")
    engine = create_engine(settings)

    try:
        with engine.connect() as connection:
            assert (
                connection.exec_driver_sql("PRAGMA journal_mode").scalar_one()
                == "delete"
            )
    finally:
        engine.dispose()

    assert not settings.database_path.with_name(
        f"{settings.database_path.name}-wal"
    ).exists()
    assert not settings.database_path.with_name(
        f"{settings.database_path.name}-shm"
    ).exists()


def test_symlinked_database_file_is_rejected_without_mutating_target(
    tmp_path: Path,
) -> None:
    settings = BenchwarmerSettings(data_root=tmp_path / "private")
    settings.initialize()
    target = tmp_path / "outside.sqlite3"
    target.write_bytes(b"outside data")
    target.chmod(0o644)
    settings.database_path.symlink_to(target)

    with pytest.raises(ConfigurationError, match="database file must not be a symlink"):
        create_engine(settings)

    assert target.read_bytes() == b"outside data"
    assert stat.S_IMODE(target.stat().st_mode) == 0o644


def test_special_database_file_is_rejected_without_blocking(tmp_path: Path) -> None:
    if not hasattr(os, "mkfifo"):
        pytest.skip("this platform does not support named pipes")

    settings = BenchwarmerSettings(data_root=tmp_path / "private")
    settings.initialize()
    os.mkfifo(settings.database_path)

    with pytest.raises(ConfigurationError, match="not a regular file"):
        create_engine(settings)
