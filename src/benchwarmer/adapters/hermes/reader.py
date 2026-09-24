"""Read a supported Hermes SQLite store without modifying it."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import sqlite3
import stat
from types import MappingProxyType
from typing import Mapping
from urllib.parse import quote

from benchwarmer.sqlite_runtime import require_wal_safe_sqlite

from .capabilities import (
    ADAPTER_VERSION,
    CAPABILITY_MANIFEST_VERSION,
    HermesCapabilityError,
    TableCapability,
    manifest_for_schema,
)


class HermesReadError(ValueError):
    """Raised for bounded Hermes source access errors."""


@dataclass(frozen=True, slots=True)
class HermesReadRequest:
    """Explicit operator-owned input for one read-only Hermes snapshot."""

    database_path: Path = field(repr=False)
    application_version: str | None = None

    def __post_init__(self) -> None:
        if (
            not isinstance(self.database_path, Path)
            or not self.database_path.is_absolute()
        ):
            raise HermesReadError("Hermes database path must be absolute")
        if self.application_version is not None and (
            not isinstance(self.application_version, str)
            or not self.application_version.strip()
        ):
            raise HermesReadError("invalid Hermes application version")


@dataclass(frozen=True, slots=True)
class HermesReadResult:
    """One immutable raw snapshot suitable for a later private importer."""

    application_version: str | None
    schema_version: int
    adapter_version: str
    capability_manifest_version: int
    journal_mode: str
    coverage: Mapping[str, str] = field(repr=False)
    tables: Mapping[str, tuple[Mapping[str, object], ...]] = field(repr=False)


def _quoted_identifier(name: str) -> str:
    """Quote a schema-derived SQLite identifier; values are always parameters."""
    return '"' + name.replace('"', '""') + '"'


def _source_uri(path: Path) -> str:
    return f"file:{quote(str(path))}?mode=ro"


def _source_identity(path: Path) -> tuple[int, int]:
    """Reject a final symlink and return its regular-file identity.

    The configured path is operator-owned. Parent-directory symlinks remain
    valid because standard macOS application paths may contain them.
    """
    try:
        path_stat = path.lstat()
    except OSError:
        path_stat = None
    if path_stat is None:
        raise HermesReadError("Hermes database is not usable")
    if stat.S_ISLNK(path_stat.st_mode) or not stat.S_ISREG(path_stat.st_mode):
        raise HermesReadError("Hermes database is not a usable regular file")
    return (path_stat.st_dev, path_stat.st_ino)


def _verify_identity(path: Path, expected: tuple[int, int]) -> None:
    if _source_identity(path) != expected:
        raise HermesReadError("Hermes database changed during snapshot")


def _schema_version(connection: sqlite3.Connection) -> int:
    try:
        rows = connection.execute(
            "SELECT version FROM schema_version LIMIT 2"
        ).fetchall()
    except sqlite3.Error:
        rows = None
    if rows is None:
        raise HermesCapabilityError("invalid Hermes schema version table")
    if len(rows) != 1 or len(rows[0]) != 1:
        raise HermesCapabilityError("invalid Hermes schema version")
    value = rows[0][0]
    if isinstance(value, bool) or not isinstance(value, int):
        raise HermesCapabilityError("invalid Hermes schema version")
    return value


def _table_names(connection: sqlite3.Connection) -> set[str]:
    return {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
        if isinstance(row[0], str)
    }


def _columns(connection: sqlite3.Connection, table: str) -> dict[str, int]:
    rows = connection.execute(
        "SELECT name, pk FROM pragma_table_info(?)", (table,)
    ).fetchall()
    return {
        name: position
        for name, position in rows
        if isinstance(name, str) and isinstance(position, int)
    }


def _foreign_keys(
    connection: sqlite3.Connection, table: str
) -> set[tuple[str, str, str]]:
    rows = connection.execute(
        'SELECT "from", "table", "to" FROM pragma_foreign_key_list(?)', (table,)
    ).fetchall()
    return {
        (column, target_table, target_column)
        for column, target_table, target_column in rows
        if all(
            isinstance(value, str) for value in (column, target_table, target_column)
        )
    }


def _validate_table(
    connection: sqlite3.Connection,
    capability: TableCapability,
    names: set[str],
    coverage: dict[str, str],
) -> None:
    if capability.name not in names:
        if capability.required:
            raise HermesCapabilityError(
                f"missing required Hermes table: {capability.name}"
            )
        coverage[f"table.{capability.name}"] = "unavailable"
        return
    coverage[f"table.{capability.name}"] = "available"
    columns = _columns(connection, capability.name)
    missing = sorted(capability.required_columns - columns.keys())
    if missing:
        raise HermesCapabilityError(
            f"missing required Hermes column: {capability.name}.{missing[0]}"
        )
    primary_key = tuple(
        name
        for name, position in sorted(columns.items(), key=lambda item: item[1])
        if position
    )
    if primary_key != capability.primary_key:
        raise HermesCapabilityError(
            f"incompatible Hermes primary key: {capability.name}"
        )
    foreign_keys = _foreign_keys(connection, capability.name)
    for column, target in capability.foreign_keys.items():
        if (column, *target) not in foreign_keys:
            raise HermesCapabilityError(
                f"missing required Hermes relationship: {capability.name}.{column}"
            )
    known = capability.required_columns | capability.optional_columns
    for column in capability.optional_columns:
        coverage[f"column.{capability.name}.{column}"] = (
            "available" if column in columns else "unavailable"
        )
    for column in columns.keys() - known:
        coverage[f"column.{capability.name}.{column}"] = "unknown"


def _validate_manifest(
    connection: sqlite3.Connection, schema_version: int
) -> tuple[Mapping[str, TableCapability], dict[str, str]]:
    manifest = manifest_for_schema(schema_version)
    coverage: dict[str, str] = {}
    names = _table_names(connection)
    for capability in manifest.values():
        _validate_table(connection, capability, names, coverage)
    return manifest, coverage


def _rows(
    connection: sqlite3.Connection, capability: TableCapability
) -> tuple[Mapping[str, object], ...]:
    columns = _columns(connection, capability.name)
    selected_columns = tuple(sorted(columns))
    selected = ", ".join(_quoted_identifier(column) for column in selected_columns)
    order = ", ".join(_quoted_identifier(column) for column in capability.primary_key)
    # nosemgrep: python.lang.security.audit.formatted-sql-query.formatted-sql-query
    cursor = connection.execute(
        f"SELECT {selected} FROM {_quoted_identifier(capability.name)} ORDER BY {order}"
    )
    try:
        return tuple(
            MappingProxyType(dict(zip(selected_columns, row, strict=True)))
            for row in cursor
        )
    finally:
        cursor.close()


def _open_source(path: Path) -> sqlite3.Connection:
    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(_source_uri(path), uri=True)
        connection.execute("PRAGMA query_only = ON")
        query_only = connection.execute("PRAGMA query_only").fetchone()
    except sqlite3.Error:
        query_only = None
    if connection is None or query_only is None:
        if connection is not None:
            connection.close()
        raise HermesReadError("unable to open Hermes database read-only")
    if query_only[0] != 1:
        connection.close()
        raise HermesReadError("unable to enforce Hermes read-only mode")

    try:
        journal = connection.execute("PRAGMA journal_mode").fetchone()
        connection.execute("BEGIN")
    except sqlite3.Error:
        connection.close()
        journal = None
    if journal is None:
        raise HermesReadError("unable to open Hermes database read-only")
    if not isinstance(journal[0], str) or journal[0].lower() != "wal":
        connection.close()
        raise HermesCapabilityError("Hermes database is not in WAL mode")
    return connection


def read_hermes_snapshot(request: HermesReadRequest) -> HermesReadResult:
    """Return one manifest-validated, read-only SQLite snapshot."""
    require_wal_safe_sqlite()
    identity = _source_identity(request.database_path)
    connection = _open_source(request.database_path)
    result: HermesReadResult | None = None
    read_failed = False
    try:
        schema_version = _schema_version(connection)
        manifest, coverage = _validate_manifest(connection, schema_version)
        _verify_identity(request.database_path, identity)
        names = _table_names(connection)
        tables = {
            capability.name: _rows(connection, capability)
            for capability in manifest.values()
            if capability.name in names
        }
        _verify_identity(request.database_path, identity)
        result = HermesReadResult(
            request.application_version,
            schema_version,
            ADAPTER_VERSION,
            CAPABILITY_MANIFEST_VERSION,
            "wal",
            MappingProxyType(dict(sorted(coverage.items()))),
            MappingProxyType(dict(sorted(tables.items()))),
        )
    except (HermesReadError, HermesCapabilityError):
        raise
    except sqlite3.Error:
        read_failed = True
    finally:
        try:
            connection.rollback()
        except sqlite3.Error:
            pass
        connection.close()
    if read_failed or result is None:
        raise HermesReadError("unable to read Hermes database")
    return result
