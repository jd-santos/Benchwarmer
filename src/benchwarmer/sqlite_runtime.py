"""Validate the SQLite library linked into the current Python process."""

import sqlite3

_WAL_SAFE_SQLITE_VERSIONS = (
    "3.51.3+, 3.50.7+ on the 3.50 branch, or 3.44.6+ on the 3.44 branch"
)


def sqlite_has_wal_reset_fix(version: tuple[int, int, int]) -> bool:
    """Return whether an SQLite version contains the WAL-reset fix."""
    if (
        not isinstance(version, tuple)
        or len(version) != 3
        or any(type(component) is not int or component < 0 for component in version)
    ):
        return False

    return (
        version >= (3, 51, 3)
        or (version[:2] == (3, 50) and version[2] >= 7)
        or (version[:2] == (3, 44) and version[2] >= 6)
    )


def require_wal_safe_sqlite() -> None:
    """Abort unless this process links an SQLite build safe for WAL use."""
    if sqlite_has_wal_reset_fix(sqlite3.sqlite_version_info):
        return

    raise RuntimeError(
        "WAL safety gate blocked linked SQLite "
        f"{sqlite3.sqlite_version}; accepted versions are "
        f"{_WAL_SAFE_SQLITE_VERSIONS}"
    )
