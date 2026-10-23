"""Create Benchwarmer's FastAPI application."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import os
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict

from benchwarmer.api.routes.bundles import create_bundles_router
from benchwarmer.api.routes.conversations import create_conversations_router
from benchwarmer.api.routes.fixtures import create_fixtures_router
from benchwarmer.api.routes.model_work import create_model_work_router
from benchwarmer.api.routes.runs import create_runs_router
from benchwarmer.api.routes.sources import create_sources_router
from benchwarmer.config import BenchwarmerSettings, ConfigurationError
from benchwarmer.db import create_engine, create_session_factory, current_revision
from benchwarmer.services.model_catalog import ModelCatalogService
from benchwarmer.services.model_work_plans import PlanRunner, mark_interrupted


class HealthResponse(BaseModel):
    """Describe the current service and database migration state."""

    model_config = ConfigDict(extra="forbid", strict=True)

    status: Literal["ok"]
    alembic_revision: str | None
    data_root_writable: Literal[True]


def create_app(
    settings: BenchwarmerSettings | None = None,
    ui_root: Path | None = None,
    *,
    plan_runner: PlanRunner | None = None,
    model_catalog: ModelCatalogService | None = None,
) -> FastAPI:
    """Create the HTTP application with explicit settings and optional built UI."""
    environment_app = settings is None
    resolved_settings = (
        BenchwarmerSettings.from_environment() if environment_app else settings
    )
    resolved_ui_root = _resolve_ui_root(ui_root, environment_app=environment_app)
    runner = plan_runner or PlanRunner(resolved_settings)
    catalog = model_catalog or ModelCatalogService(resolved_settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        # A plan that was running when the last process stopped is interrupted,
        # never rerun on its own. Done at startup, not at construction, so that
        # building the app touches nothing on disk.
        _recover_interrupted_plans(resolved_settings)
        yield
        runner.terminate_all()

    app = FastAPI(lifespan=lifespan)
    router = APIRouter(prefix="/api/v1")

    @router.get("/health", response_model=HealthResponse)
    def get_health() -> HealthResponse:
        engine = create_engine(resolved_settings)
        try:
            revision = current_revision(engine)
        finally:
            engine.dispose()
        return HealthResponse(
            status="ok",
            alembic_revision=revision,
            data_root_writable=True,
        )

    router.include_router(create_sources_router(resolved_settings))
    router.include_router(create_conversations_router(resolved_settings))
    router.include_router(create_bundles_router(resolved_settings))
    router.include_router(create_fixtures_router())
    router.include_router(create_runs_router(resolved_settings))
    router.include_router(create_model_work_router(resolved_settings, runner, catalog))
    app.include_router(router)

    if resolved_ui_root is not None:

        @app.api_route(
            "/{requested_path:path}", methods=["GET", "HEAD"], include_in_schema=False
        )
        def serve_ui(requested_path: str) -> FileResponse:
            return _serve_ui_file(resolved_ui_root, requested_path)

    return app


def _recover_interrupted_plans(settings: BenchwarmerSettings) -> None:
    """Mark plans left ``running`` by an earlier process as interrupted."""
    try:
        engine = create_engine(settings)
    except Exception:  # noqa: BLE001 - startup must not fail on an unprovisioned data root
        return
    try:
        if current_revision(engine) is None:
            return
        with create_session_factory(engine)() as session:
            mark_interrupted(session)
    except Exception:  # noqa: BLE001 - an older schema without the table is not fatal here
        return
    finally:
        engine.dispose()


def _resolve_ui_root(ui_root: Path | None, *, environment_app: bool) -> Path | None:
    """Resolve and validate the generated UI directory for this app mode."""
    configured_root = ui_root
    if configured_root is None and environment_app:
        raw_root = os.environ.get("BENCHWARMER_UI_ROOT")
        if raw_root is None:
            raise ConfigurationError(
                "BENCHWARMER_UI_ROOT is required when starting the application"
            )
        configured_root = Path(raw_root)
    if configured_root is None:
        return None
    if not configured_root.is_absolute():
        raise ConfigurationError("BENCHWARMER_UI_ROOT must be an absolute path")

    resolved_root = configured_root.resolve()
    if not resolved_root.is_dir():
        raise ConfigurationError("BENCHWARMER_UI_ROOT must be an existing directory")
    if not (resolved_root / "200.html").is_file():
        raise ConfigurationError("BENCHWARMER_UI_ROOT must contain 200.html")
    return resolved_root


def _serve_ui_file(ui_root: Path, requested_path: str) -> FileResponse:
    """Serve generated assets or the SPA document without masking API failures."""
    if requested_path == "api" or requested_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="API endpoint not found")

    candidate = (ui_root / requested_path).resolve()
    if not candidate.is_relative_to(ui_root):
        raise HTTPException(status_code=404, detail="UI asset not found")
    if candidate.is_file():
        return FileResponse(candidate)

    top_level = requested_path.partition("/")[0]
    if Path(requested_path).suffix or (top_level and (ui_root / top_level).is_dir()):
        raise HTTPException(status_code=404, detail="UI asset not found")

    return FileResponse(ui_root / "200.html")
