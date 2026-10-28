"""The ``benchwarmer`` command: ``init`` writes settings, ``serve`` starts the app."""

from __future__ import annotations

import io
import os
from pathlib import Path
import stat
import subprocess
import tomllib
from typing import Any

import pytest

from benchwarmer import cli
from benchwarmer.config import BenchwarmerSettings

_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def _run(argv: list[str], environ: dict[str, str], home: Path, **extra: Any):
    out, err = io.StringIO(), io.StringIO()
    code = cli.main(
        argv,
        environ=environ,
        platform_name="darwin",
        home=home,
        stdout=out,
        stderr=err,
        **extra,
    )
    return code, out.getvalue(), err.getvalue()


def _built_ui(path: Path) -> Path:
    path.mkdir(parents=True)
    (path / "200.html").write_text("<html></html>")
    return path


def _migrate(root: Path) -> None:
    result = subprocess.run(
        ["uv", "run", "alembic", "upgrade", "head"],
        cwd=_REPOSITORY_ROOT,
        env=os.environ | {"BENCHWARMER_DATA_ROOT": str(root)},
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


class _Server:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def __call__(self, app: Any, **kwargs: Any) -> None:
        self.calls.append({"app": app, **kwargs})


# --- init --------------------------------------------------------------------


def test_init_writes_a_commented_example_into_the_data_root(tmp_path: Path) -> None:
    home = tmp_path / "home"
    data_root = tmp_path / "data"
    environ = {"BENCHWARMER_DATA_ROOT": str(data_root)}

    code, out, err = _run(["init"], environ, home)

    assert (code, err) == (0, "")
    path = data_root / "benchwarmer.toml"
    assert out == f"wrote {path}\n"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(data_root.stat().st_mode) == 0o700
    text = path.read_text()
    assert str(data_root) in text
    assert "docs/configuration.md" in text

    parsed = tomllib.loads(text)
    assert parsed == {
        "paths": {"import_roots": []},
        "server": {"host": "127.0.0.1", "port": 8000},
        "providers": {"allow": [], "deny": []},
    }
    settings = BenchwarmerSettings.from_environment(
        environ, platform_name="darwin", home=home
    )
    assert settings.config_path == path
    assert settings == BenchwarmerSettings(data_root=data_root, config_path=path)


def test_init_refuses_to_overwrite_an_existing_file(tmp_path: Path) -> None:
    home = tmp_path / "home"
    data_root = tmp_path / "data"
    data_root.mkdir(mode=0o700)
    path = data_root / "benchwarmer.toml"
    path.write_text("[server]\nport = 9000\n")
    environ = {"BENCHWARMER_DATA_ROOT": str(data_root)}

    code, out, err = _run(["init"], environ, home)

    assert code == 1
    assert out == ""
    assert "already exists" in err
    assert path.read_text() == "[server]\nport = 9000\n"


def test_init_honours_benchwarmer_config_and_needs_its_directory(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    target = tmp_path / "etc" / "benchwarmer.toml"
    environ = {"BENCHWARMER_CONFIG": str(target)}

    code, _, err = _run(["init"], environ, home)
    assert code == 1
    assert "does not exist; create it first" in err
    assert not target.exists()

    target.parent.mkdir()
    code, out, err = _run(["init"], environ, home)
    assert (code, err) == (0, "")
    assert out == f"wrote {target}\n"
    assert (
        BenchwarmerSettings.from_environment(
            environ, platform_name="darwin", home=home
        ).config_path
        == target
    )


# --- serve -------------------------------------------------------------------


def test_serve_needs_a_built_ui(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(cli, "CHECKOUT_ROOT", tmp_path / "not-a-checkout")
    data_root = tmp_path / "data"
    server = _Server()

    code, out, err = _run(
        ["serve"],
        {"BENCHWARMER_DATA_ROOT": str(data_root)},
        tmp_path / "home",
        run_server=server,
    )

    assert code == 1
    assert out == ""
    assert "no built UI" in err
    assert "npm --prefix web run build" in err
    assert str(data_root / "benchwarmer.toml") in err
    assert server.calls == []
    assert not data_root.exists()


def test_serve_refuses_an_unmigrated_data_root_without_touching_it(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "data"
    ui = _built_ui(tmp_path / "ui")
    server = _Server()

    code, out, err = _run(
        ["serve"],
        {"BENCHWARMER_DATA_ROOT": str(data_root), "BENCHWARMER_UI_ROOT": str(ui)},
        tmp_path / "home",
        run_server=server,
    )

    assert code == 1
    assert "has no database yet" in err
    assert "uv run alembic upgrade head" in err
    assert "never migrates" in err
    assert server.calls == []
    assert not data_root.exists()


def test_serve_uses_the_checkout_build_when_present(
    tmp_path: Path, monkeypatch
) -> None:
    checkout = tmp_path / "checkout"
    build = _built_ui(checkout / "web" / "build")
    monkeypatch.setattr(cli, "CHECKOUT_ROOT", checkout)
    data_root = tmp_path / "data"
    _migrate(data_root)

    code, out, err = _run(
        ["serve", "--check"],
        {"BENCHWARMER_DATA_ROOT": str(data_root)},
        tmp_path / "home",
        run_server=_Server(),
    )

    assert (code, err) == (0, "")
    assert f"UI root: {build}" in out


def test_serve_check_prints_the_resolved_settings_and_starts_nothing(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "data"
    _migrate(data_root)
    ui = _built_ui(tmp_path / "ui")
    harness = tmp_path / "harness"
    harness.mkdir()
    (data_root / "benchwarmer.toml").write_text(
        f"""
        [paths]
        ui_root = "{ui}"
        harness_dir = "{harness}"
        import_roots = ["{tmp_path / "inbox"}"]

        [server]
        port = 8123

        [providers]
        allow = ["anthropic", "openrouter"]
        """
    )
    server = _Server()

    code, out, err = _run(
        ["serve", "--check"],
        {"BENCHWARMER_DATA_ROOT": str(data_root)},
        tmp_path / "home",
        run_server=server,
    )

    assert (code, err) == (0, "")
    assert out.splitlines() == [
        f"settings file: {data_root / 'benchwarmer.toml'}",
        f"data root: {data_root}",
        f"UI root: {ui}",
        f"harness: {harness}",
        f"import roots: {tmp_path / 'inbox'}",
        "provider allow list: anthropic, openrouter",
        "provider deny list: none",
        "listen: http://127.0.0.1:8123/",
    ]
    assert server.calls == []


def test_serve_starts_uvicorn_with_the_configured_or_overridden_address(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "data"
    _migrate(data_root)
    ui = _built_ui(tmp_path / "ui")
    environ = {
        "BENCHWARMER_DATA_ROOT": str(data_root),
        "BENCHWARMER_UI_ROOT": str(ui),
        "BENCHWARMER_PORT": "8123",
    }
    server = _Server()

    code, out, err = _run(["serve"], environ, tmp_path / "home", run_server=server)
    assert (code, err) == (0, "")
    assert "settings file: none" in out
    assert "harness: not configured" in out
    assert "listen: http://127.0.0.1:8123/" in out
    assert len(server.calls) == 1
    call = server.calls[0]
    assert (call["host"], call["port"]) == ("127.0.0.1", 8123)
    assert call["app"].title == "FastAPI"

    code, out, err = _run(
        ["serve", "--host", "0.0.0.0", "--port", "9000"],
        environ,
        tmp_path / "home",
        run_server=server,
    )
    assert (code, err) == (0, "")
    assert "listen: http://0.0.0.0:9000/" in out
    assert (server.calls[1]["host"], server.calls[1]["port"]) == ("0.0.0.0", 9000)

    code, _, err = _run(
        ["serve", "--port", "0"], environ, tmp_path / "home", run_server=server
    )
    assert code == 1
    assert "--port must be an integer" in err
    assert len(server.calls) == 2


def test_console_script_is_installed() -> None:
    result = subprocess.run(
        ["uv", "run", "benchwarmer", "--help"],
        cwd=_REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "serve" in result.stdout
    assert "init" in result.stdout


@pytest.mark.parametrize("command", ["serve", "init"])
def test_configuration_errors_exit_with_one_line(command: str, tmp_path: Path) -> None:
    code, out, err = _run(
        [command], {"BENCHWARMER_DATA_ROOT": "relative"}, tmp_path / "home"
    )

    assert code == 1
    assert out == ""
    assert err == "benchwarmer: BENCHWARMER_DATA_ROOT must be an absolute path\n"
