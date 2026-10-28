"""The ``benchwarmer`` command: start the application or write a settings file.

``benchwarmer serve`` loads settings (environment over ``benchwarmer.toml``
over defaults), finds the built UI, checks that the data root is migrated,
and runs Uvicorn in the foreground. It never migrates the database and never
starts model work; approved plans still begin only from the Bundles page
(ADR 0006). ``benchwarmer init`` writes a commented example settings file.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping, Sequence
import os
from pathlib import Path
import sys
from typing import Any, TextIO

from benchwarmer.config import (
    CONFIG_FILE_NAME,
    DEFAULT_HOST,
    DEFAULT_PORT,
    BenchwarmerSettings,
    ConfigurationError,
    default_data_root,
    settings_file_path,
)

# The checkout this package was imported from, when it is one. A built UI at
# web/build and the Alembic scripts at migrations/ are looked up here; an
# installed wheel has neither and must configure them explicitly.
CHECKOUT_ROOT = Path(__file__).resolve().parents[2]

ServerRunner = Callable[..., Any]


def main(
    argv: Sequence[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    platform_name: str | None = None,
    home: Path | None = None,
    run_server: ServerRunner | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    """Entry point for the console script; returns the process exit status."""
    out = sys.stdout if stdout is None else stdout
    err = sys.stderr if stderr is None else stderr
    parser = _parser()
    args = parser.parse_args(list(sys.argv[1:] if argv is None else argv))
    environment = os.environ if environ is None else environ
    current_platform = sys.platform if platform_name is None else platform_name
    current_home = Path.home() if home is None else home
    try:
        if args.command == "serve":
            return _serve(
                args,
                environment,
                platform_name=current_platform,
                home=current_home,
                run_server=run_server,
                out=out,
            )
        return _init(
            environment, platform_name=current_platform, home=current_home, out=out
        )
    except ConfigurationError as error:
        err.write(f"benchwarmer: {error}\n")
        return 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="benchwarmer",
        description="Run Benchwarmer or write its settings file.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    serve = commands.add_parser(
        "serve",
        help="start the application with the configured host and port",
        description=(
            "Load settings, resolve the built UI, check the data root is "
            "migrated, and start Uvicorn in the foreground."
        ),
    )
    serve.add_argument("--host", help="listen address (overrides the settings)")
    serve.add_argument("--port", type=int, help="listen port (overrides the settings)")
    serve.add_argument(
        "--check",
        action="store_true",
        help="print the resolved settings and findings, then exit without serving",
    )
    commands.add_parser(
        "init",
        help=f"write a commented example {CONFIG_FILE_NAME} without overwriting",
        description=(
            f"Write a commented example {CONFIG_FILE_NAME} to the data root, "
            "or to BENCHWARMER_CONFIG when set. An existing file is left alone."
        ),
    )
    return parser


def _serve(
    args: argparse.Namespace,
    environment: Mapping[str, str],
    *,
    platform_name: str,
    home: Path,
    run_server: ServerRunner | None,
    out: TextIO,
) -> int:
    settings = BenchwarmerSettings.from_environment(
        environment, platform_name=platform_name, home=home
    )
    host = settings.host if args.host is None else args.host
    port = settings.port if args.port is None else args.port
    if not 1 <= port <= 65535:
        raise ConfigurationError("--port must be an integer from 1 through 65535")

    ui_root = resolve_ui_root(settings)
    _require_migrated_data_root(settings)

    lines = [
        f"settings file: {settings.config_path or 'none'}",
        f"data root: {settings.data_root}",
        f"UI root: {ui_root}",
        "harness: "
        + (
            str(settings.harness_dir)
            if settings.harness_dir is not None
            else "not configured; plans can be previewed but not started here"
        ),
        "import roots: "
        + (
            ", ".join(str(root) for root in settings.import_roots)
            if settings.import_roots
            else "none"
        ),
        f"provider allow list: {', '.join(settings.provider_allow) or 'every provider'}",
        f"provider deny list: {', '.join(settings.provider_deny) or 'none'}",
        f"listen: http://{host}:{port}/",
    ]
    out.write("\n".join(lines) + "\n")
    out.flush()
    if args.check:
        return 0

    from benchwarmer.api.app import create_app

    app = create_app(settings, ui_root=ui_root)
    if run_server is None:
        import uvicorn

        run_server = uvicorn.run
    run_server(app, host=host, port=port, log_level="info")
    return 0


def resolve_ui_root(settings: BenchwarmerSettings) -> Path:
    """The configured UI root, or the checkout's ``web/build`` when it is built."""
    if settings.ui_root is not None:
        return settings.ui_root
    checkout_build = CHECKOUT_ROOT / "web" / "build"
    if (checkout_build / "200.html").is_file():
        return checkout_build
    where = settings.config_path or settings_hint(settings)
    raise ConfigurationError(
        "no built UI: build it with `npm --prefix web run build`, or set "
        f"[paths] ui_root in {where} or BENCHWARMER_UI_ROOT"
    )


def settings_hint(settings: BenchwarmerSettings) -> Path:
    """Where a settings file would be read from for these settings."""
    return settings.data_root / CONFIG_FILE_NAME


def _require_migrated_data_root(settings: BenchwarmerSettings) -> None:
    """Refuse an absent or outdated database; the fix is always a manual command."""
    fix = (
        "run `uv run alembic upgrade head` from the checkout with the same "
        "settings; serve never migrates on its own"
    )
    if not settings.database_path.is_file():
        raise ConfigurationError(
            f"the data root {settings.data_root} has no database yet; {fix}"
        )

    from benchwarmer.db import create_engine, current_revision

    engine = create_engine(settings)
    try:
        current = current_revision(engine)
    finally:
        engine.dispose()
    if current is None:
        raise ConfigurationError(
            f"the database at {settings.database_path} is not migrated; {fix}"
        )
    head = _packaged_head()
    if head is not None and current != head:
        raise ConfigurationError(
            f"the database at {settings.database_path} is at revision {current} "
            f"but this checkout's head is {head}; {fix}"
        )


def _packaged_head() -> str | None:
    """The newest Alembic revision in this checkout, or None outside a checkout."""
    migrations = CHECKOUT_ROOT / "migrations"
    if not (migrations / "env.py").is_file():
        return None
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    config = Config()
    config.set_main_option("script_location", str(migrations))
    return ScriptDirectory.from_config(config).get_current_head()


def _init(
    environment: Mapping[str, str],
    *,
    platform_name: str,
    home: Path,
    out: TextIO,
) -> int:
    target = settings_file_path(environment, platform_name=platform_name, home=home)
    if target.exists():
        raise ConfigurationError(
            f"{target} already exists; edit it in place or move it aside first"
        )
    data_root = default_data_root(environment, platform_name=platform_name, home=home)
    if target.parent == data_root:
        # The default location is inside the data root, which is created with
        # the same private layout the application uses.
        BenchwarmerSettings(data_root=data_root).initialize()
    elif not target.parent.is_dir():
        raise ConfigurationError(
            f"the directory for {target} does not exist; create it first"
        )
    content = example_settings(data_root)
    try:
        descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        raise ConfigurationError(
            f"{target} already exists; edit it in place or move it aside first"
        ) from None
    except OSError as error:
        raise ConfigurationError(f"could not write {target}: {error}") from error
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(content)
    out.write(f"wrote {target}\n")
    return 0


def example_settings(data_root: Path) -> str:
    """A commented example settings file; every key is optional."""
    return f"""\
# Benchwarmer settings. Environment variables override these values; see
# docs/configuration.md for every key, its variable, and its default.
# Paths must be absolute; a leading "~" means the current user's home.

[paths]
# Where the database, snapshots, logs, and other private data live.
# Default: this file's own directory.
# data_root = "{data_root}"

# Directories on this host the web app may import conversation files from.
# Default: none (no host-local import).
import_roots = []

# The checkout's harness/ package. Setting it lets the app start plans the
# operator approved in the Bundles page; unset, plans can only be previewed.
# harness_dir = "/path/to/Benchwarmer/harness"

# The built Svelte application (the directory holding 200.html).
# Default: web/build inside the checkout when it has been built.
# ui_root = "/path/to/Benchwarmer/web/build"

[server]
host = "{DEFAULT_HOST}"
port = {DEFAULT_PORT}

[providers]
# Provider ids the harness may register. An empty allow list means every
# provider the harness knows; deny removes ids from whatever allow leaves.
allow = []
deny = []
"""
