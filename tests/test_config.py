from __future__ import annotations

import os
from pathlib import Path
import stat
import subprocess
import sys

import pytest
from pydantic import ValidationError

from benchwarmer.config import BenchwarmerSettings, ConfigurationError


def test_macos_default_uses_current_home_without_creating_files(tmp_path: Path) -> None:
    home = tmp_path / "home"

    settings = BenchwarmerSettings.from_environment(
        {}, platform_name="darwin", home=home
    )

    assert settings.data_root == home / "Library/Application Support/Benchwarmer"
    assert not home.exists()


def test_override_expands_only_current_user_tilde(tmp_path: Path) -> None:
    home = tmp_path / "home"

    settings = BenchwarmerSettings.from_environment(
        {"BENCHWARMER_DATA_ROOT": "~/private/benchwarmer"},
        platform_name="darwin",
        home=home,
    )

    assert settings.data_root == home / "private/benchwarmer"


def test_override_does_not_expand_environment_variable_syntax(tmp_path: Path) -> None:
    configured = tmp_path / "$HOME/benchwarmer"

    settings = BenchwarmerSettings.from_environment(
        {"BENCHWARMER_DATA_ROOT": str(configured), "HOME": "/ignored"},
        platform_name="darwin",
        home=tmp_path / "home",
    )

    assert settings.data_root == configured


@pytest.mark.parametrize("value", ["", "   ", "relative/path", "~//tmp"])
def test_invalid_override_fails_with_actionable_error(
    value: str, tmp_path: Path
) -> None:
    with pytest.raises(ConfigurationError, match="BENCHWARMER_DATA_ROOT"):
        BenchwarmerSettings.from_environment(
            {"BENCHWARMER_DATA_ROOT": value},
            platform_name="darwin",
            home=tmp_path / "home",
        )


def test_non_macos_resolution_uses_absolute_xdg_or_home_fallback(
    tmp_path: Path,
) -> None:
    xdg = tmp_path / "xdg"
    home = tmp_path / "home"

    configured = BenchwarmerSettings.from_environment(
        {"XDG_DATA_HOME": str(xdg)}, platform_name="linux", home=home
    )
    fallback = BenchwarmerSettings.from_environment(
        {}, platform_name="linux", home=home
    )

    assert configured.data_root == xdg / "benchwarmer"
    assert fallback.data_root == home / ".local/share/benchwarmer"


@pytest.mark.parametrize("value", ["", "relative/xdg"])
def test_invalid_xdg_data_home_is_rejected(value: str, tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError, match="XDG_DATA_HOME"):
        BenchwarmerSettings.from_environment(
            {"XDG_DATA_HOME": value},
            platform_name="linux",
            home=tmp_path / "home",
        )


def test_settings_resolve_the_fixed_private_layout(tmp_path: Path) -> None:
    settings = BenchwarmerSettings(data_root=tmp_path / "private")

    assert settings.database_dir == settings.data_root / "database"
    assert settings.database_path == settings.database_dir / "benchwarmer.sqlite3"
    assert settings.artifacts_dir == settings.data_root / "artifacts"
    assert settings.snapshots_dir == settings.data_root / "snapshots"
    assert settings.jobs_dir == settings.data_root / "jobs"
    assert settings.job_staging_dir == settings.jobs_dir / "staging"
    assert settings.job_workspaces_dir == settings.jobs_dir / "workspaces"
    assert settings.logs_dir == settings.data_root / "logs"
    assert settings.locks_dir == settings.data_root / "locks"
    assert not settings.data_root.exists()


def test_initialization_creates_owner_only_directories_and_no_database(
    tmp_path: Path,
) -> None:
    settings = BenchwarmerSettings(data_root=tmp_path / "private")

    returned = settings.initialize()

    assert returned is settings
    for directory in settings.directories:
        assert directory.is_dir()
        assert stat.S_IMODE(directory.stat().st_mode) == 0o700
    assert not settings.database_path.exists()


def test_import_has_no_filesystem_side_effects(tmp_path: Path) -> None:
    root = tmp_path / "must-not-exist"
    environment = dict(os.environ)
    environment["BENCHWARMER_DATA_ROOT"] = str(root)

    subprocess.run(
        [sys.executable, "-c", "import benchwarmer.config"],
        check=True,
        env=environment,
    )

    assert not root.exists()


def test_existing_file_is_rejected_as_data_root(tmp_path: Path) -> None:
    root = tmp_path / "not-a-directory"
    root.write_text("fixture\n", encoding="utf-8")
    settings = BenchwarmerSettings(data_root=root)

    with pytest.raises(ConfigurationError, match="not a directory"):
        settings.initialize()


def test_non_writable_root_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "private"
    root.mkdir(mode=0o700)
    root.chmod(0o500)
    settings = BenchwarmerSettings(data_root=root)

    try:
        with pytest.raises(ConfigurationError, match="not writable"):
            settings.initialize()
    finally:
        root.chmod(0o700)


def test_symlinked_data_root_is_rejected_without_mutating_target(
    tmp_path: Path,
) -> None:
    outside = tmp_path / "outside"
    outside.mkdir(mode=0o755)
    outside.chmod(0o755)
    root = tmp_path / "private"
    root.symlink_to(outside, target_is_directory=True)
    settings = BenchwarmerSettings(data_root=root)

    with pytest.raises(ConfigurationError, match="symlink"):
        settings.initialize()

    assert stat.S_IMODE(outside.stat().st_mode) == 0o755
    assert list(outside.iterdir()) == []


def test_symlinked_layout_child_is_rejected_without_mutating_target(
    tmp_path: Path,
) -> None:
    root = tmp_path / "private"
    root.mkdir(mode=0o700)
    outside = tmp_path / "outside"
    outside.mkdir(mode=0o755)
    outside.chmod(0o755)
    (root / "artifacts").symlink_to(outside, target_is_directory=True)
    settings = BenchwarmerSettings(data_root=root)

    with pytest.raises(ConfigurationError, match="artifacts.*symlink"):
        settings.initialize()

    assert stat.S_IMODE(outside.stat().st_mode) == 0o755
    assert list(outside.iterdir()) == []


def test_settings_are_frozen(tmp_path: Path) -> None:
    settings = BenchwarmerSettings(data_root=tmp_path / "private")

    with pytest.raises(ValidationError):
        setattr(settings, "data_root", tmp_path / "other")
