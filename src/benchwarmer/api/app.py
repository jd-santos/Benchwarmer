"""Create Benchwarmer's FastAPI application."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict

from benchwarmer.api.routes.sources import create_sources_router
from benchwarmer.config import BenchwarmerSettings, ConfigurationError
from benchwarmer.db import create_engine, current_revision


class HealthResponse(BaseModel):
    """Describe the current service and database migration state."""

    model_config = ConfigDict(extra="forbid", strict=True)

    status: Literal["ok"]
    alembic_revision: str | None
    data_root_writable: Literal[True]


def create_app(
    settings: BenchwarmerSettings | None = None,
    ui_root: Path | None = None,
) -> FastAPI:
    """Create the HTTP application with explicit settings and optional built UI."""
    environment_app = settings is None
    resolved_settings = (
        BenchwarmerSettings.from_environment() if environment_app else settings
    )
    resolved_ui_root = _resolve_ui_root(ui_root, environment_app=environment_app)
    app = FastAPI()
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
    app.include_router(router)

    if resolved_ui_root is not None:

        @app.api_route(
            "/{requested_path:path}", methods=["GET", "HEAD"], include_in_schema=False
        )
        def serve_ui(requested_path: str) -> FileResponse:
            return _serve_ui_file(resolved_ui_root, requested_path)

    return app


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
