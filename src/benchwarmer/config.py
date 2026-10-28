"""Resolve and initialize Benchwarmer's private runtime paths and settings.

Settings come from three layers. Environment variables win, then the
``benchwarmer.toml`` settings file, then the built-in defaults. The file lives
at the data root unless ``BENCHWARMER_CONFIG`` names another location.
Reading settings never creates anything on disk.
"""

from __future__ import annotations

from collections.abc import Mapping
import os
from pathlib import Path
import secrets
import stat
import sys
import tomllib
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, field_validator

_CONFIG_VARIABLE = "BENCHWARMER_CONFIG"
_DATA_ROOT_VARIABLE = "BENCHWARMER_DATA_ROOT"
_IMPORT_ROOTS_VARIABLE = "BENCHWARMER_IMPORT_ROOTS"
_HARNESS_DIR_VARIABLE = "BENCHWARMER_HARNESS_DIR"
_UI_ROOT_VARIABLE = "BENCHWARMER_UI_ROOT"
_HOST_VARIABLE = "BENCHWARMER_HOST"
_PORT_VARIABLE = "BENCHWARMER_PORT"
_PROVIDER_ALLOW_VARIABLE = "BENCHWARMER_PROVIDER_ALLOW"
_PROVIDER_DENY_VARIABLE = "BENCHWARMER_PROVIDER_DENY"
_XDG_DATA_HOME_VARIABLE = "XDG_DATA_HOME"

CONFIG_FILE_NAME = "benchwarmer.toml"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000

# Every section and key the settings file may contain. Anything else is
# refused by name so a typo cannot silently fall back to a default.
_FILE_SCHEMA: Mapping[str, frozenset[str]] = {
    "paths": frozenset({"data_root", "import_roots", "harness_dir", "ui_root"}),
    "server": frozenset({"host", "port"}),
    "providers": frozenset({"allow", "deny"}),
}


class ConfigurationError(RuntimeError):
    """Report an invalid or unusable runtime configuration."""


class BenchwarmerSettings(BaseModel):
    """Resolved settings with explicit, side-effect-free construction."""

    model_config = ConfigDict(frozen=True)

    data_root: Path
    # Directories on this host that the web app may import conversation files
    # from. Empty means no host-local import; collectors push everything else.
    import_roots: tuple[Path, ...] = ()
    # The checkout's harness/ package, when the app may start approved harness
    # runs itself. None means plans can be previewed but not executed here.
    harness_dir: Path | None = None
    # The built Svelte application (the directory holding 200.html). None means
    # the API serves no UI unless a caller passes one explicitly.
    ui_root: Path | None = None
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    # Provider ids the harness may register. An empty allow list means every
    # provider the harness knows; deny removes ids from whatever allow leaves.
    provider_allow: tuple[str, ...] = ()
    provider_deny: tuple[str, ...] = ()
    # The settings file these values were read from, or None when there was none.
    config_path: Path | None = None

    @field_validator("data_root")
    @classmethod
    def _require_absolute_data_root(cls, value: Path) -> Path:
        if not value.is_absolute():
            raise ValueError("data_root must be an absolute path")
        return value

    @field_validator("import_roots")
    @classmethod
    def _require_absolute_import_roots(
        cls, value: tuple[Path, ...]
    ) -> tuple[Path, ...]:
        if any(not root.is_absolute() for root in value):
            raise ValueError("import_roots must be absolute paths")
        return value

    @field_validator("harness_dir")
    @classmethod
    def _require_absolute_harness_dir(cls, value: Path | None) -> Path | None:
        if value is not None and not value.is_absolute():
            raise ValueError("harness_dir must be an absolute path")
        return value

    @field_validator("ui_root")
    @classmethod
    def _require_absolute_ui_root(cls, value: Path | None) -> Path | None:
        if value is not None and not value.is_absolute():
            raise ValueError("ui_root must be an absolute path")
        return value

    @field_validator("port")
    @classmethod
    def _require_valid_port(cls, value: int) -> int:
        if not 1 <= value <= 65535:
            raise ValueError("port must be an integer from 1 through 65535")
        return value

    @field_validator("host")
    @classmethod
    def _require_host(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("host must not be empty")
        return value

    @classmethod
    def from_environment(
        cls,
        environ: Mapping[str, str] | None = None,
        *,
        platform_name: str | None = None,
        home: Path | None = None,
    ) -> Self:
        """Resolve settings from the environment, the settings file, and defaults."""
        environment = os.environ if environ is None else environ
        current_platform = sys.platform if platform_name is None else platform_name
        current_home = Path.home() if home is None else home
        if not current_home.is_absolute():
            raise ConfigurationError("the current home directory must be absolute")

        default_root = default_data_root(
            environment, platform_name=current_platform, home=current_home
        )
        file_path = settings_file_path(
            environment, platform_name=current_platform, home=current_home
        )
        explicit_file = _CONFIG_VARIABLE in environment
        if explicit_file and not file_path.is_file():
            raise ConfigurationError(
                f"{_CONFIG_VARIABLE} names a settings file that does not exist: "
                f"{file_path}"
            )
        file = _SettingsFile.read(file_path) if file_path.is_file() else None

        paths = file.section("paths") if file else {}
        server = file.section("server") if file else {}
        providers = file.section("providers") if file else {}

        if _DATA_ROOT_VARIABLE in environment:
            root = _path_value(
                environment[_DATA_ROOT_VARIABLE], current_home, _DATA_ROOT_VARIABLE
            )
        elif file and "data_root" in paths:
            root = file.path("paths", "data_root", current_home)
        else:
            root = default_root

        if _IMPORT_ROOTS_VARIABLE in environment:
            import_roots = _path_list(
                environment[_IMPORT_ROOTS_VARIABLE].split(os.pathsep),
                current_home,
                _IMPORT_ROOTS_VARIABLE,
            )
        elif file and "import_roots" in paths:
            import_roots = file.path_list("paths", "import_roots", current_home)
        else:
            import_roots = ()

        harness_dir = _layered_optional_path(
            environment, file, _HARNESS_DIR_VARIABLE, "harness_dir", current_home
        )
        ui_root = _layered_optional_path(
            environment, file, _UI_ROOT_VARIABLE, "ui_root", current_home
        )

        if _HOST_VARIABLE in environment:
            host = environment[_HOST_VARIABLE].strip()
            if not host:
                raise ConfigurationError(f"{_HOST_VARIABLE} must not be empty")
        elif file and "host" in server:
            host = file.string("server", "host")
        else:
            host = DEFAULT_HOST

        if _PORT_VARIABLE in environment:
            port = _port_value(environment[_PORT_VARIABLE], _PORT_VARIABLE)
        elif file and "port" in server:
            port = file.port("server", "port")
        else:
            port = DEFAULT_PORT

        if _PROVIDER_ALLOW_VARIABLE in environment:
            allow = _provider_ids(
                environment[_PROVIDER_ALLOW_VARIABLE].split(","),
                _PROVIDER_ALLOW_VARIABLE,
            )
        elif file and "allow" in providers:
            allow = file.provider_ids("providers", "allow")
        else:
            allow = ()

        if _PROVIDER_DENY_VARIABLE in environment:
            deny = _provider_ids(
                environment[_PROVIDER_DENY_VARIABLE].split(","),
                _PROVIDER_DENY_VARIABLE,
            )
        elif file and "deny" in providers:
            deny = file.provider_ids("providers", "deny")
        else:
            deny = ()

        return cls(
            data_root=root,
            import_roots=import_roots,
            harness_dir=harness_dir,
            ui_root=ui_root,
            host=host,
            port=port,
            provider_allow=allow,
            provider_deny=deny,
            config_path=file.path_on_disk if file else None,
        )

    def provider_environment(self) -> dict[str, str]:
        """Variables that hand the provider lists to a harness process.

        Both are always set, so a harness started by the application sees
        exactly these settings and nothing inherited from the shell.
        """
        return {
            _PROVIDER_ALLOW_VARIABLE: ",".join(self.provider_allow),
            _PROVIDER_DENY_VARIABLE: ",".join(self.provider_deny),
        }

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


def default_data_root(
    environ: Mapping[str, str],
    *,
    platform_name: str,
    home: Path,
) -> Path:
    """The data root before the settings file is consulted.

    ``BENCHWARMER_DATA_ROOT`` when set, otherwise the platform's per-user
    application data directory.
    """
    if _DATA_ROOT_VARIABLE in environ:
        return _path_value(environ[_DATA_ROOT_VARIABLE], home, _DATA_ROOT_VARIABLE)
    if platform_name == "darwin":
        return home / "Library/Application Support/Benchwarmer"
    return _non_macos_data_root(environ, home)


def settings_file_path(
    environ: Mapping[str, str],
    *,
    platform_name: str,
    home: Path,
) -> Path:
    """Where the settings file is read from, whether or not it exists."""
    if _CONFIG_VARIABLE in environ:
        return _path_value(environ[_CONFIG_VARIABLE], home, _CONFIG_VARIABLE)
    root = default_data_root(environ, platform_name=platform_name, home=home)
    return root / CONFIG_FILE_NAME


class _SettingsFile:
    """A parsed and structurally validated ``benchwarmer.toml``."""

    def __init__(self, path_on_disk: Path, data: Mapping[str, Any]) -> None:
        self.path_on_disk = path_on_disk
        self._data = data

    @classmethod
    def read(cls, path: Path) -> _SettingsFile:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as error:
            raise ConfigurationError(f"could not read {path}: {error}") from error
        try:
            data = tomllib.loads(text)
        except tomllib.TOMLDecodeError as error:
            raise ConfigurationError(f"could not parse {path}: {error}") from error
        for section, value in data.items():
            if section not in _FILE_SCHEMA:
                expected = ", ".join(f"[{name}]" for name in _FILE_SCHEMA)
                raise ConfigurationError(
                    f"{path}: unknown section [{section}]; expected one of {expected}"
                )
            if not isinstance(value, dict):
                raise ConfigurationError(f"{path}: [{section}] must be a table")
            for key in value:
                if key not in _FILE_SCHEMA[section]:
                    expected = ", ".join(sorted(_FILE_SCHEMA[section]))
                    raise ConfigurationError(
                        f"{path}: unknown key [{section}] {key}; "
                        f"expected one of {expected}"
                    )
        return cls(path, data)

    def section(self, name: str) -> Mapping[str, Any]:
        value = self._data.get(name, {})
        return value if isinstance(value, dict) else {}

    def _label(self, section: str, key: str) -> str:
        return f"{self.path_on_disk}: [{section}] {key}"

    def string(self, section: str, key: str) -> str:
        value = self.section(section)[key]
        label = self._label(section, key)
        if not isinstance(value, str):
            raise ConfigurationError(f"{label} must be a string")
        if not value.strip():
            raise ConfigurationError(f"{label} must not be empty")
        return value

    def path(self, section: str, key: str, home: Path) -> Path:
        return _path_value(self.string(section, key), home, self._label(section, key))

    def path_list(self, section: str, key: str, home: Path) -> tuple[Path, ...]:
        value = self.section(section)[key]
        label = self._label(section, key)
        if not isinstance(value, list) or any(
            not isinstance(item, str) for item in value
        ):
            raise ConfigurationError(f"{label} must be an array of strings")
        return _path_list(value, home, label)

    def port(self, section: str, key: str) -> int:
        value = self.section(section)[key]
        label = self._label(section, key)
        if isinstance(value, bool) or not isinstance(value, int):
            raise ConfigurationError(f"{label} must be an integer from 1 through 65535")
        return _port_value(str(value), label)

    def provider_ids(self, section: str, key: str) -> tuple[str, ...]:
        value = self.section(section)[key]
        label = self._label(section, key)
        if not isinstance(value, list) or any(
            not isinstance(item, str) for item in value
        ):
            raise ConfigurationError(f"{label} must be an array of provider ids")
        if any(not item.strip() for item in value):
            raise ConfigurationError(f"{label} must not contain empty provider ids")
        return _provider_ids(value, label)


def _layered_optional_path(
    environment: Mapping[str, str],
    file: _SettingsFile | None,
    variable: str,
    key: str,
    home: Path,
) -> Path | None:
    """An optional path: environment first, then ``[paths]`` in the file."""
    if variable in environment:
        raw = environment[variable]
        if not raw.strip():
            return None
        return _path_value(raw, home, variable)
    if file and key in file.section("paths"):
        return file.path("paths", key, home)
    return None


def _path_value(raw_value: str, home: Path, label: str) -> Path:
    """One absolute path; a leading ``~`` means the current user's home."""
    if not raw_value.strip():
        raise ConfigurationError(f"{label} must not be empty")

    if raw_value == "~":
        path = home
    elif raw_value.startswith("~/"):
        relative = raw_value[2:]
        if relative.startswith("/"):
            raise ConfigurationError(f"{label} must use a single slash after '~'")
        path = home / relative
    else:
        path = Path(raw_value)

    if not path.is_absolute():
        raise ConfigurationError(f"{label} must be an absolute path")
    return path


def _path_list(parts: list[str], home: Path, label: str) -> tuple[Path, ...]:
    """Absolute paths, skipping blank entries; relative entries are refused."""
    roots: list[Path] = []
    for part in parts:
        if not part.strip():
            continue
        if part == "~":
            root = home
        elif part.startswith("~/"):
            root = home / part[2:]
        else:
            root = Path(part)
        if not root.is_absolute():
            raise ConfigurationError(f"{label} entries must be absolute paths")
        roots.append(root)
    return tuple(roots)


def _port_value(raw_value: str, label: str) -> int:
    try:
        port = int(raw_value.strip())
    except ValueError:
        raise ConfigurationError(
            f"{label} must be an integer from 1 through 65535"
        ) from None
    if not 1 <= port <= 65535:
        raise ConfigurationError(f"{label} must be an integer from 1 through 65535")
    return port


def _provider_ids(parts: list[str], label: str) -> tuple[str, ...]:
    """Trimmed, de-duplicated provider ids in the order given; blanks are skipped."""
    ids: list[str] = []
    for part in parts:
        item = part.strip()
        if not item:
            continue
        if any(character.isspace() for character in item) or "," in item:
            raise ConfigurationError(
                f"{label} entries must be single provider ids without spaces"
            )
        if item not in ids:
            ids.append(item)
    return tuple(ids)


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
