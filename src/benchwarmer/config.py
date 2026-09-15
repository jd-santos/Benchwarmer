"""Resolve and initialize Benchwarmer's private runtime paths."""

from __future__ import annotations

from collections.abc import Mapping
import os
from pathlib import Path
import secrets
import stat
import sys
from typing import Self

from pydantic import BaseModel, ConfigDict, field_validator

_DATA_ROOT_VARIABLE = "BENCHWARMER_DATA_ROOT"
_XDG_DATA_HOME_VARIABLE = "XDG_DATA_HOME"


class ConfigurationError(RuntimeError):
    """Report an invalid or unusable runtime configuration."""


class BenchwarmerSettings(BaseModel):
    """Resolved private paths with explicit, side-effect-free construction."""

    model_config = ConfigDict(frozen=True)

    data_root: Path

    @field_validator("data_root")
    @classmethod
    def _require_absolute_data_root(cls, value: Path) -> Path:
        if not value.is_absolute():
            raise ValueError("data_root must be an absolute path")
        return value

    @classmethod
    def from_environment(
        cls,
        environ: Mapping[str, str] | None = None,
        *,
        platform_name: str | None = None,
        home: Path | None = None,
    ) -> Self:
        """Resolve settings from explicit inputs or the current process."""
        environment = os.environ if environ is None else environ
        current_platform = sys.platform if platform_name is None else platform_name
        current_home = Path.home() if home is None else home
        if not current_home.is_absolute():
            raise ConfigurationError("the current home directory must be absolute")

        if _DATA_ROOT_VARIABLE in environment:
            root = _explicit_data_root(environment[_DATA_ROOT_VARIABLE], current_home)
        elif current_platform == "darwin":
            root = current_home / "Library/Application Support/Benchwarmer"
        else:
            root = _non_macos_data_root(environment, current_home)

        return cls(data_root=root)

    @property
    def database_dir(self) -> Path:
        return self.data_root / "database"

    @property
    def database_path(self) -> Path:
        return self.database_dir / "benchwarmer.sqlite3"

    @property
    def artifacts_dir(self) -> Path:
        return self.data_root / "artifacts"

    @property
    def snapshots_dir(self) -> Path:
        return self.data_root / "snapshots"

    @property
    def jobs_dir(self) -> Path:
        return self.data_root / "jobs"

    @property
    def job_staging_dir(self) -> Path:
        return self.jobs_dir / "staging"

    @property
    def job_workspaces_dir(self) -> Path:
        return self.jobs_dir / "workspaces"

    @property
    def logs_dir(self) -> Path:
        return self.data_root / "logs"

    @property
    def locks_dir(self) -> Path:
        return self.data_root / "locks"

    @property
    def directories(self) -> tuple[Path, ...]:
        """Return private directories in parent-before-child creation order."""
        return (
            self.data_root,
            self.database_dir,
            self.artifacts_dir,
            self.snapshots_dir,
            self.jobs_dir,
            self.job_staging_dir,
            self.job_workspaces_dir,
            self.logs_dir,
            self.locks_dir,
        )

    def initialize(self) -> Self:
        """Create and validate the private directory layout."""
        for directory in self.directories:
            relative = directory.relative_to(self.data_root)
            label = "data root" if relative == Path(".") else relative.as_posix()
            _prepare_private_directory(directory, label)
        return self


def _explicit_data_root(raw_value: str, home: Path) -> Path:
    if not raw_value.strip():
        raise ConfigurationError(f"{_DATA_ROOT_VARIABLE} must not be empty")

    if raw_value == "~":
        root = home
    elif raw_value.startswith("~/"):
        relative = raw_value[2:]
        if relative.startswith("/"):
            raise ConfigurationError(
                f"{_DATA_ROOT_VARIABLE} must use a single slash after '~'"
            )
        root = home / relative
    else:
        root = Path(raw_value)

    if not root.is_absolute():
        raise ConfigurationError(f"{_DATA_ROOT_VARIABLE} must be an absolute path")
    return root


def _non_macos_data_root(environment: Mapping[str, str], home: Path) -> Path:
    if _XDG_DATA_HOME_VARIABLE not in environment:
        return home / ".local/share/benchwarmer"

    raw_value = environment[_XDG_DATA_HOME_VARIABLE]
    if not raw_value.strip():
        raise ConfigurationError(f"{_XDG_DATA_HOME_VARIABLE} must not be empty")

    xdg_root = Path(raw_value)
    if not xdg_root.is_absolute():
        raise ConfigurationError(f"{_XDG_DATA_HOME_VARIABLE} must be an absolute path")
    return xdg_root / "benchwarmer"


def _prepare_private_directory(directory: Path, label: str) -> None:
    if directory.is_symlink():
        raise ConfigurationError(
            f"private data directory '{label}' must not be a symlink"
        )

    existed = directory.exists()
    if existed:
        if not directory.is_dir():
            raise ConfigurationError(
                f"private data path '{label}' exists but is not a directory"
            )
        if stat.S_IMODE(directory.stat().st_mode) & 0o222 == 0:
            raise ConfigurationError(
                f"private data directory '{label}' is not writable"
            )

    try:
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    except OSError as error:
        raise ConfigurationError(
            f"could not create private data directory '{label}'"
        ) from error

    if directory.is_symlink():
        raise ConfigurationError(
            f"private data directory '{label}' must not be a symlink"
        )

    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(directory, flags)
    except OSError as error:
        raise ConfigurationError(
            f"could not securely open private data directory '{label}'"
        ) from error

    try:
        if not stat.S_ISDIR(os.fstat(descriptor).st_mode):
            raise ConfigurationError(
                f"private data path '{label}' exists but is not a directory"
            )
        os.fchmod(descriptor, 0o700)
        _verify_directory_writable(descriptor, label)
    except OSError as error:
        raise ConfigurationError(
            f"could not secure private data directory '{label}'"
        ) from error
    finally:
        os.close(descriptor)


def _verify_directory_writable(directory_descriptor: int, label: str) -> None:
    probe_name = f".benchwarmer-write-check-{secrets.token_hex(8)}"
    probe_descriptor: int | None = None
    try:
        probe_descriptor = os.open(
            probe_name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
            dir_fd=directory_descriptor,
        )
        os.fchmod(probe_descriptor, 0o600)
    except OSError as error:
        raise ConfigurationError(
            f"private data directory '{label}' is not writable"
        ) from error
    finally:
        if probe_descriptor is not None:
            os.close(probe_descriptor)
            try:
                os.unlink(probe_name, dir_fd=directory_descriptor)
            except OSError as error:
                raise ConfigurationError(
                    "could not remove write check from private data directory "
                    f"'{label}'"
                ) from error
