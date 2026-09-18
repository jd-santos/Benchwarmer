"""Create Benchwarmer's FastAPI application."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, FastAPI
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


def create_app(settings: BenchwarmerSettings | None = None) -> FastAPI:
    """Create the HTTP application with explicit or environment settings."""
    resolved_settings = (
        BenchwarmerSettings.from_environment() if settings is None else settings
    )
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
    return app
