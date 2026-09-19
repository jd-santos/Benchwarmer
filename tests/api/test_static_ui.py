from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from benchwarmer.api.app import create_app
from benchwarmer.config import BenchwarmerSettings, ConfigurationError


def _client(tmp_path: Path, ui_root: Path) -> TestClient:
    return TestClient(
        create_app(BenchwarmerSettings(data_root=tmp_path / "private"), ui_root=ui_root)
    )


def _built_ui(tmp_path: Path) -> Path:
    root = tmp_path / "ui"
    root.mkdir()
    (root / "200.html").write_text("<html><body>application</body></html>")
    (root / "assets").mkdir()
    (root / "assets" / "app.js").write_text("console.log('asset');")
    return root


def test_serves_exact_built_assets_and_spa_fallback(tmp_path: Path) -> None:
    client = _client(tmp_path, _built_ui(tmp_path))

    asset = client.get("/assets/app.js")
    route = client.get("/sources")
    root = client.head("/")

    assert asset.status_code == 200
    assert asset.text == "console.log('asset');"
    assert asset.headers["content-type"].startswith("text/javascript")
    assert route.status_code == 200
    assert route.text == "<html><body>application</body></html>"
    assert route.headers["content-type"].startswith("text/html")
    assert root.status_code == 200
    assert root.text == ""


def test_static_fallback_does_not_mask_api_or_asset_errors(tmp_path: Path) -> None:
    client = _client(tmp_path, _built_ui(tmp_path))

    assert client.get("/api").status_code == 404
    assert client.get("/api/not-real").status_code == 404
    assert client.post("/api/v1/not-real").status_code == 405
    assert client.get("/assets/missing.js").status_code == 404
    assert client.get("/assets/missing").status_code == 404
    assert client.post("/sources").status_code == 405


def test_static_fallback_rejects_paths_outside_the_built_ui(tmp_path: Path) -> None:
    ui_root = _built_ui(tmp_path)
    secret = tmp_path / "secret.txt"
    secret.write_text("do not serve")
    client = _client(tmp_path, ui_root)

    response = client.get("/%2e%2e/secret.txt")

    assert response.status_code == 404
    assert "do not serve" not in response.text


def test_explicit_settings_allow_api_only_construction(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("BENCHWARMER_UI_ROOT", str(_built_ui(tmp_path)))
    settings = BenchwarmerSettings(data_root=tmp_path / "private")

    assert TestClient(create_app(settings)).get("/").status_code == 404


def test_environment_app_requires_valid_built_ui(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("BENCHWARMER_DATA_ROOT", str(tmp_path / "private"))
    monkeypatch.delenv("BENCHWARMER_UI_ROOT", raising=False)
    with pytest.raises(ConfigurationError, match="BENCHWARMER_UI_ROOT is required"):
        create_app()

    monkeypatch.setenv("BENCHWARMER_UI_ROOT", "relative/build")
    with pytest.raises(ConfigurationError, match="must be an absolute path"):
        create_app()

    missing_root = tmp_path / "missing"
    monkeypatch.setenv("BENCHWARMER_UI_ROOT", str(missing_root))
    with pytest.raises(ConfigurationError, match="must be an existing directory"):
        create_app()

    empty_root = tmp_path / "empty"
    empty_root.mkdir()
    monkeypatch.setenv("BENCHWARMER_UI_ROOT", str(empty_root))
    with pytest.raises(ConfigurationError, match="must contain 200.html"):
        create_app()

    built_ui = _built_ui(tmp_path)
    monkeypatch.setenv("BENCHWARMER_UI_ROOT", str(built_ui))
    assert TestClient(create_app()).get("/").status_code == 200
