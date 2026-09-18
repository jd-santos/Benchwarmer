"""Create and inspect Benchwarmer's configured SQLite database."""

from __future__ import annotations

import os
from pathlib import Path
import stat

from alembic.runtime.migration import MigrationContext
from sqlalchemy import URL, create_engine as sqlalchemy_create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from benchwarmer.config import BenchwarmerSettings, ConfigurationError
from benchwarmer.sqlite_runtime import require_wal_safe_sqlite


def database_url(settings: BenchwarmerSettings) -> URL:
    """Return the SQLite URL for the configured private database path."""
    return URL.create(
        drivername="sqlite+pysqlite", database=str(settings.database_path)
    )


def create_engine(settings: BenchwarmerSettings) -> Engine:
    """Create a synchronous engine for the configured SQLite database."""
    require_wal_safe_sqlite()
    settings.initialize()
    database_path = settings.database_path
    _secure_database_file(database_path)

    engine = sqlalchemy_create_engine(database_url(settings))
    event.listen(engine, "do_connect", _verify_connection_preconditions(database_path))
    event.listen(engine, "connect", _enable_sqlite_foreign_keys)
    return engine


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Create sessions for short-lived synchronous units of work."""
    return sessionmaker(bind=engine)


def current_revision(engine: Engine) -> str | None:
    """Return the applied Alembic revision, or None for an unmigrated database."""
    with engine.connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()


def _enable_sqlite_foreign_keys(connection: object, record: object) -> None:
    """Enable SQLite foreign-key enforcement for every DBAPI connection."""
    del record
    cursor = connection.cursor()  # type: ignore[attr-defined]
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
    finally:
        cursor.close()


def _verify_connection_preconditions(database_path: Path):
    def verify_connection(
        dialect: object,
        connection_record: object,
        connection_arguments: list[object],
        connection_keyword_arguments: dict[str, object],
    ) -> None:
        del (
            dialect,
            connection_record,
            connection_arguments,
            connection_keyword_arguments,
        )
        require_wal_safe_sqlite()
        _secure_database_file(database_path)

    return verify_connection


def _secure_database_file(database_path: Path) -> None:
    if database_path.is_symlink():
        raise ConfigurationError("database file must not be a symlink")

    flags = (
        os.O_RDWR
        | os.O_CREAT
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_NONBLOCK", 0)
    )
    try:
        descriptor = os.open(database_path, flags, 0o600)
    except OSError as error:
        raise ConfigurationError("could not securely open database file") from error

    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise ConfigurationError("database path exists but is not a regular file")
        os.fchmod(descriptor, 0o600)
    except OSError as error:
        raise ConfigurationError(
            "could not secure database file permissions"
        ) from error
    finally:
        os.close(descriptor)
