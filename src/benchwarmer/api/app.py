"""Create Benchwarmer's FastAPI application."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict

from benchwarmer.api.routes.sources import create_sources_router
from benchwarmer.config import BenchwarmerSettings
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
    resolved_settings = (
        BenchwarmerSettings.from_environment() if settings is None else settings
    )
    resolved_ui_root = _resolve_ui_root(ui_root)
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
        def serve_ui(requested_path: str, request: Request) -> FileResponse:
            return _serve_ui_file(resolved_ui_root, requested_path, request)

    return app


def _resolve_ui_root(ui_root: Path | None) -> Path | None:
    """Resolve an optional generated UI directory without touching the filesystem."""
    configured_root = ui_root
    if configured_root is None:
        raw_root = os.environ.get("BENCHWARMER_UI_ROOT")
        if raw_root is None:
            return None
        configured_root = Path(raw_root)
    if not configured_root.is_absolute():
        raise ValueError("BENCHWARMER_UI_ROOT must be an absolute path")
    return configured_root.resolve()


def _serve_ui_file(
    ui_root: Path, requested_path: str, request: Request
) -> FileResponse:
    """Serve generated assets or the SPA document without masking API failures."""
    if requested_path == "api" or requested_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="API endpoint not found")

    candidate = (ui_root / requested_path).resolve()
    if not candidate.is_relative_to(ui_root):
        raise HTTPException(status_code=404, detail="UI asset not found")
    if candidate.is_file():
        return FileResponse(candidate)

    if Path(requested_path).suffix:
        raise HTTPException(status_code=404, detail="UI asset not found")

    fallback = ui_root / "200.html"
    if not fallback.is_file():
        raise HTTPException(status_code=404, detail="UI is not built")
    return FileResponse(fallback)
