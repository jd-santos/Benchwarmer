#!/usr/bin/env python3
"""Validate the exact provisioned Python runtime used by Benchwarmer."""

from __future__ import annotations

import importlib
import sys
from collections.abc import Sequence


REQUIRED_MODULES = (
    "bz2",
    "ctypes",
    "curses",
    "hashlib",
    "lzma",
    "readline",
    "sqlite3",
    "ssl",
    "zlib",
)


def validate_runtime(expected_python: str, expected_sqlite: str) -> str:
    """Return a runtime summary or raise when any pinned requirement is unmet."""
    modules = {}
    for name in REQUIRED_MODULES:
        try:
            modules[name] = importlib.import_module(name)
        except ImportError as error:
            raise RuntimeError(f"required module {name} is unavailable") from error

    observed_python = sys.version.split()[0]
    if observed_python != expected_python:
        raise RuntimeError(
            f"expected Python {expected_python}, found Python {observed_python}"
        )

    sqlite3 = modules["sqlite3"]
    observed_sqlite = sqlite3.sqlite_version
    if observed_sqlite != expected_sqlite:
        raise RuntimeError(
            f"expected SQLite {expected_sqlite}, found SQLite {observed_sqlite}"
        )

    ssl = modules["ssl"]
    openssl_version = ssl.OPENSSL_VERSION
    openssl_info = ssl.OPENSSL_VERSION_INFO
    if not openssl_version.startswith("OpenSSL ") or openssl_info[0] != 3:
        raise RuntimeError(
            f"expected OpenSSL major 3, found {openssl_version} ({openssl_info!r})"
        )

    return (
        f"Python {observed_python}; SQLite {observed_sqlite}; {openssl_version}; "
        "required stdlib modules: ok"
    )


def main(arguments: Sequence[str] | None = None) -> int:
    """Run validation as a command-line program."""
    args = list(sys.argv[1:] if arguments is None else arguments)
    if len(args) != 2:
        print(
            "usage: validate-python-runtime.py EXPECTED_PYTHON EXPECTED_SQLITE",
            file=sys.stderr,
        )
        return 2

    try:
        summary = validate_runtime(args[0], args[1])
    except RuntimeError as error:
        print(f"runtime validation failed: {error}", file=sys.stderr)
        return 1

    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
