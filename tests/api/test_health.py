import os
from pathlib import Path
import subprocess
import sys

from fastapi.testclient import TestClient

from benchwarmer.api.app import create_app
from benchwarmer.config import BenchwarmerSettings


_REPOSITORY_ROOT = Path(__file__).parents[2]


def _upgrade_database(root: Path) -> subprocess.CompletedProcess[str]:
    environment = os.environ | {"BENCHWARMER_DATA_ROOT": str(root)}
    return subprocess.run(
        ["uv", "run", "alembic", "upgrade", "head"],
        cwd=_REPOSITORY_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )


def test_health_reports_an_unmigrated_private_database(tmp_path: Path) -> None:
    settings = BenchwarmerSettings(data_root=tmp_path / "private")
    client = TestClient(create_app(settings))

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert set(response.json()) == {"status", "alembic_revision", "data_root_writable"}
    assert response.json() == {
        "status": "ok",
        "alembic_revision": None,
        "data_root_writable": True,
    }


def test_health_reports_the_real_revision_of_a_migrated_database(
    tmp_path: Path,
) -> None:
    root = tmp_path / "private"
    upgrade = _upgrade_database(root)
    assert upgrade.returncode == 0, upgrade.stderr
    client = TestClient(create_app(BenchwarmerSettings(data_root=root)))

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "alembic_revision": "0002",
        "data_root_writable": True,
    }


def test_factory_resolves_environment_settings_when_omitted(
    monkeypatch, tmp_path: Path
) -> None:
    root = tmp_path / "private"
    ui_root = tmp_path / "ui"
    ui_root.mkdir()
    (ui_root / "200.html").write_text("<html></html>")
    monkeypatch.setenv("BENCHWARMER_DATA_ROOT", str(root))
    monkeypatch.setenv("BENCHWARMER_UI_ROOT", str(ui_root))
    app = create_app()

    assert not root.exists()

    client = TestClient(app)
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert root.exists()


def test_health_inspects_the_database_on_each_request(
    monkeypatch, tmp_path: Path
) -> None:
    settings = BenchwarmerSettings(data_root=tmp_path / "private")
    calls: list[str] = []

    class Engine:
        def dispose(self) -> None:
            calls.append("dispose")

    def create_test_engine(received_settings: BenchwarmerSettings) -> Engine:
        assert received_settings is settings
        calls.append("create")
        return Engine()

    revisions = iter(["review-sentinel", None])

    def inspect_revision(engine: Engine) -> str | None:
        del engine
        calls.append("revision")
        return next(revisions)

    monkeypatch.setattr("benchwarmer.api.app.create_engine", create_test_engine)
    monkeypatch.setattr("benchwarmer.api.app.current_revision", inspect_revision)
    client = TestClient(create_app(settings))

    first_response = client.get("/api/v1/health")
    second_response = client.get("/api/v1/health")

    assert first_response.status_code == 200
    assert first_response.json()["alembic_revision"] == "review-sentinel"
    assert second_response.status_code == 200
    assert second_response.json()["alembic_revision"] is None
    assert calls == ["create", "revision", "dispose"] * 2


def test_health_disposes_the_engine_when_revision_inspection_fails(
    monkeypatch, tmp_path: Path
) -> None:
    settings = BenchwarmerSettings(data_root=tmp_path / "private")
    disposed = False

    class Engine:
        def dispose(self) -> None:
            nonlocal disposed
            disposed = True

    monkeypatch.setattr("benchwarmer.api.app.create_engine", lambda _: Engine())

    def fail_revision(engine: Engine) -> None:
        del engine
        raise RuntimeError("database unavailable")

    monkeypatch.setattr("benchwarmer.api.app.current_revision", fail_revision)
    client = TestClient(create_app(settings), raise_server_exceptions=False)

    response = client.get("/api/v1/health")

    assert response.status_code == 500
    assert disposed
    assert "status" not in response.text


def test_health_does_not_fabricate_a_response_on_engine_failure(
    monkeypatch, tmp_path: Path
) -> None:
    settings = BenchwarmerSettings(data_root=tmp_path / "private")

    def fail_engine(_: BenchwarmerSettings) -> None:
        raise RuntimeError("configuration unavailable")

    monkeypatch.setattr("benchwarmer.api.app.create_engine", fail_engine)
    client = TestClient(create_app(settings), raise_server_exceptions=False)

    response = client.get("/api/v1/health")

    assert response.status_code == 500
    assert "status" not in response.text


def test_importing_the_application_module_has_no_filesystem_side_effects(
    tmp_path: Path,
) -> None:
    root = tmp_path / "private"
    environment = os.environ | {"BENCHWARMER_DATA_ROOT": str(root)}

    result = subprocess.run(
        [sys.executable, "-c", "import benchwarmer.api.app"],
        check=False,
        capture_output=True,
        env=environment,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert not root.exists()


def test_generated_api_documentation_endpoints_remain_available(tmp_path: Path) -> None:
    client = TestClient(create_app(BenchwarmerSettings(data_root=tmp_path / "private")))

    assert client.get("/docs").status_code == 200
    assert client.get("/redoc").status_code == 200
    openapi = client.get("/openapi.json")
    assert openapi.status_code == 200
    assert "/api/v1/health" in openapi.json()["paths"]


def test_health_only_accepts_get(tmp_path: Path) -> None:
    client = TestClient(create_app(BenchwarmerSettings(data_root=tmp_path / "private")))

    assert client.post("/api/v1/health").status_code == 405
