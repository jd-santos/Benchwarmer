"""The ``benchwarmer.toml`` settings file: loading, precedence, and errors."""

from __future__ import annotations

from pathlib import Path

import pytest

from benchwarmer.config import (
    BenchwarmerSettings,
    ConfigurationError,
    settings_file_path,
)


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_without_a_settings_file_every_new_setting_has_its_default(
    tmp_path: Path,
) -> None:
    settings = BenchwarmerSettings.from_environment(
        {"BENCHWARMER_DATA_ROOT": str(tmp_path / "data")},
        platform_name="darwin",
        home=tmp_path / "home",
    )

    assert settings.config_path is None
    assert settings.ui_root is None
    assert settings.host == "127.0.0.1"
    assert settings.port == 8000
    assert settings.provider_allow == ()
    assert settings.provider_deny == ()
    assert settings.provider_environment() == {
        "BENCHWARMER_PROVIDER_ALLOW": "",
        "BENCHWARMER_PROVIDER_DENY": "",
    }


def test_settings_file_location_follows_the_data_root_or_the_variable(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    assert (
        settings_file_path({}, platform_name="darwin", home=home)
        == home / "Library/Application Support/Benchwarmer/benchwarmer.toml"
    )
    assert (
        settings_file_path(
            {"BENCHWARMER_DATA_ROOT": str(tmp_path / "data")},
            platform_name="linux",
            home=home,
        )
        == tmp_path / "data/benchwarmer.toml"
    )
    assert (
        settings_file_path(
            {"BENCHWARMER_CONFIG": "~/etc/bw.toml"}, platform_name="linux", home=home
        )
        == home / "etc/bw.toml"
    )


def test_settings_file_at_the_data_root_is_read_by_default(tmp_path: Path) -> None:
    home = tmp_path / "home"
    data_root = home / "Library/Application Support/Benchwarmer"
    path = _write(
        data_root / "benchwarmer.toml",
        f"""
        [paths]
        import_roots = ["~/inbox", "{tmp_path / "exports"}"]
        harness_dir = "~/Repos/Benchwarmer/harness"
        ui_root = "{tmp_path / "ui"}"

        [server]
        host = "0.0.0.0"
        port = 8765

        [providers]
        allow = ["anthropic", "openai"]
        deny = ["openai"]
        """,
    )

    settings = BenchwarmerSettings.from_environment(
        {}, platform_name="darwin", home=home
    )

    assert settings.config_path == path
    assert settings.data_root == data_root
    assert settings.import_roots == (home / "inbox", tmp_path / "exports")
    assert settings.harness_dir == home / "Repos/Benchwarmer/harness"
    assert settings.ui_root == tmp_path / "ui"
    assert settings.host == "0.0.0.0"
    assert settings.port == 8765
    assert settings.provider_allow == ("anthropic", "openai")
    assert settings.provider_deny == ("openai",)
    assert settings.provider_environment() == {
        "BENCHWARMER_PROVIDER_ALLOW": "anthropic,openai",
        "BENCHWARMER_PROVIDER_DENY": "openai",
    }


def test_settings_file_can_move_the_data_root(tmp_path: Path) -> None:
    home = tmp_path / "home"
    _write(
        home / ".local/share/benchwarmer/benchwarmer.toml",
        f'[paths]\ndata_root = "{tmp_path / "elsewhere"}"\n',
    )

    settings = BenchwarmerSettings.from_environment(
        {}, platform_name="linux", home=home
    )

    assert settings.data_root == tmp_path / "elsewhere"
    assert settings.config_path == home / ".local/share/benchwarmer/benchwarmer.toml"


def test_benchwarmer_config_names_the_file_and_must_exist(tmp_path: Path) -> None:
    home = tmp_path / "home"
    path = _write(tmp_path / "etc" / "custom.toml", "[server]\nport = 9000\n")

    settings = BenchwarmerSettings.from_environment(
        {"BENCHWARMER_CONFIG": str(path)}, platform_name="darwin", home=home
    )
    assert settings.port == 9000
    assert settings.config_path == path

    _write(home / "settings.toml", "[server]\nport = 9001\n")
    assert (
        BenchwarmerSettings.from_environment(
            {"BENCHWARMER_CONFIG": "~/settings.toml"},
            platform_name="darwin",
            home=home,
        ).port
        == 9001
    )

    with pytest.raises(ConfigurationError, match="BENCHWARMER_CONFIG.*does not exist"):
        BenchwarmerSettings.from_environment(
            {"BENCHWARMER_CONFIG": str(tmp_path / "missing.toml")},
            platform_name="darwin",
            home=home,
        )
    with pytest.raises(ConfigurationError, match="BENCHWARMER_CONFIG.*absolute"):
        BenchwarmerSettings.from_environment(
            {"BENCHWARMER_CONFIG": "relative.toml"}, platform_name="darwin", home=home
        )


def test_environment_variables_override_the_settings_file(tmp_path: Path) -> None:
    home = tmp_path / "home"
    path = _write(
        tmp_path / "benchwarmer.toml",
        f"""
        [paths]
        data_root = "{tmp_path / "file-data"}"
        import_roots = ["{tmp_path / "file-inbox"}"]
        harness_dir = "{tmp_path / "file-harness"}"
        ui_root = "{tmp_path / "file-ui"}"

        [server]
        host = "0.0.0.0"
        port = 9000

        [providers]
        allow = ["anthropic"]
        deny = ["openai"]
        """,
    )

    settings = BenchwarmerSettings.from_environment(
        {
            "BENCHWARMER_CONFIG": str(path),
            "BENCHWARMER_DATA_ROOT": str(tmp_path / "env-data"),
            "BENCHWARMER_IMPORT_ROOTS": str(tmp_path / "env-inbox"),
            "BENCHWARMER_HARNESS_DIR": str(tmp_path / "env-harness"),
            "BENCHWARMER_UI_ROOT": str(tmp_path / "env-ui"),
            "BENCHWARMER_HOST": "127.0.0.1",
            "BENCHWARMER_PORT": "8001",
            "BENCHWARMER_PROVIDER_ALLOW": "openrouter, google,,",
            "BENCHWARMER_PROVIDER_DENY": "",
        },
        platform_name="darwin",
        home=home,
    )

    assert settings.data_root == tmp_path / "env-data"
    assert settings.import_roots == (tmp_path / "env-inbox",)
    assert settings.harness_dir == tmp_path / "env-harness"
    assert settings.ui_root == tmp_path / "env-ui"
    assert settings.host == "127.0.0.1"
    assert settings.port == 8001
    assert settings.provider_allow == ("openrouter", "google")
    assert settings.provider_deny == ()


def test_an_empty_harness_dir_variable_clears_the_file_value(tmp_path: Path) -> None:
    home = tmp_path / "home"
    path = _write(
        tmp_path / "benchwarmer.toml",
        f'[paths]\nharness_dir = "{tmp_path / "harness"}"\n',
    )

    settings = BenchwarmerSettings.from_environment(
        {"BENCHWARMER_CONFIG": str(path), "BENCHWARMER_HARNESS_DIR": ""},
        platform_name="darwin",
        home=home,
    )

    assert settings.harness_dir is None


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("[paths\n", "could not parse"),
        ("[path]\ndata_root = '/x'\n", r"unknown section \[path\]"),
        ("[paths]\ndata = '/x'\n", r"unknown key \[paths\] data"),
        (
            "[paths]\ndata_root = 'relative/data'\n",
            r"\[paths\] data_root must be an absolute path",
        ),
        ("[paths]\ndata_root = ''\n", r"\[paths\] data_root must not be empty"),
        ("[paths]\ndata_root = 7\n", r"\[paths\] data_root must be a string"),
        (
            "[paths]\nimport_roots = '/x'\n",
            r"\[paths\] import_roots must be an array of strings",
        ),
        (
            "[paths]\nimport_roots = ['relative']\n",
            r"\[paths\] import_roots entries must be absolute",
        ),
        (
            "[paths]\nharness_dir = '~//x'\n",
            r"\[paths\] harness_dir must use a single slash",
        ),
        ("[paths]\nui_root = 'web/build'\n", r"\[paths\] ui_root must be an absolute"),
        (
            "[server]\nport = '8000'\n",
            r"\[server\] port must be an integer from 1 through 65535",
        ),
        (
            "[server]\nport = 70000\n",
            r"\[server\] port must be an integer from 1 through 65535",
        ),
        ("[server]\nport = true\n", r"\[server\] port must be an integer"),
        ("[server]\nhost = ''\n", r"\[server\] host must not be empty"),
        (
            "[providers]\nallow = 'anthropic'\n",
            r"\[providers\] allow must be an array of provider ids",
        ),
        ("[providers]\ndeny = ['']\n", r"\[providers\] deny must not contain empty"),
        (
            "[providers]\nallow = ['two words']\n",
            r"\[providers\] allow entries must be single provider ids",
        ),
        ("paths = 1\n", r"\[paths\] must be a table"),
    ],
)
def test_settings_file_errors_name_the_file_and_key(
    text: str, message: str, tmp_path: Path
) -> None:
    path = _write(tmp_path / "benchwarmer.toml", text)

    with pytest.raises(ConfigurationError, match=message) as info:
        BenchwarmerSettings.from_environment(
            {"BENCHWARMER_CONFIG": str(path)},
            platform_name="darwin",
            home=tmp_path / "home",
        )
    assert str(path) in str(info.value)


@pytest.mark.parametrize(
    ("variable", "value", "message"),
    [
        ("BENCHWARMER_PORT", "abc", "BENCHWARMER_PORT must be an integer"),
        ("BENCHWARMER_PORT", "0", "BENCHWARMER_PORT must be an integer"),
        ("BENCHWARMER_HOST", " ", "BENCHWARMER_HOST must not be empty"),
        (
            "BENCHWARMER_UI_ROOT",
            "web/build",
            "BENCHWARMER_UI_ROOT must be an absolute path",
        ),
        ("BENCHWARMER_PROVIDER_ALLOW", "a b", "BENCHWARMER_PROVIDER_ALLOW entries"),
    ],
)
def test_invalid_environment_values_for_new_settings_are_rejected(
    variable: str, value: str, message: str, tmp_path: Path
) -> None:
    with pytest.raises(ConfigurationError, match=message):
        BenchwarmerSettings.from_environment(
            {"BENCHWARMER_DATA_ROOT": str(tmp_path / "data"), variable: value},
            platform_name="darwin",
            home=tmp_path / "home",
        )


def test_reading_settings_creates_nothing(tmp_path: Path) -> None:
    home = tmp_path / "home"
    path = _write(tmp_path / "benchwarmer.toml", "[server]\nport = 9000\n")
    before = sorted(str(item) for item in tmp_path.rglob("*"))

    BenchwarmerSettings.from_environment(
        {"BENCHWARMER_CONFIG": str(path)}, platform_name="darwin", home=home
    )

    assert sorted(str(item) for item in tmp_path.rglob("*")) == before
    assert not home.exists()
