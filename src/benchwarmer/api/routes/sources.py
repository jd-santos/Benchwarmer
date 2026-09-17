"""Expose persisted source import status."""

from __future__ import annotations

import datetime as dt
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from benchwarmer.config import BenchwarmerSettings
from benchwarmer.db import create_engine, create_session_factory
from benchwarmer.services.source_status import list_source_status

CoverageState = Literal["available", "partial", "unavailable", "unknown"]


class SourceCoverageResponse(BaseModel):
    """Coverage states for every public source-status dimension."""

    model_config = ConfigDict(extra="forbid", strict=True)

    sessions: CoverageState
    token_usage: CoverageState
    request_ids: CoverageState
    actual_charges: CoverageState
    list_price_estimates: CoverageState
    subscription_expense: CoverageState
    quota: CoverageState
    credits: CoverageState
    prompts: CoverageState
    classifications: CoverageState


class SourceStatusResponse(BaseModel):
    """Public status for one configured source."""

    model_config = ConfigDict(extra="forbid", strict=True)

    id: str
    kind: str
    display_name: str
    last_successful_import_at: dt.datetime | None
    coverage: SourceCoverageResponse


class SourcesResponse(BaseModel):
    """Stable envelope for the configured source collection."""

    model_config = ConfigDict(extra="forbid", strict=True)

    items: list[SourceStatusResponse]


def create_sources_router(settings: BenchwarmerSettings) -> APIRouter:
    """Create the source routes for one resolved runtime configuration."""
    router = APIRouter()

    @router.get("/sources", response_model=SourcesResponse)
    def get_sources() -> SourcesResponse:
        engine = create_engine(settings)
        factory = create_session_factory(engine)
        try:
            with factory() as session:
                statuses = list_source_status(session)
                return SourcesResponse(
                    items=[
                        SourceStatusResponse(
                            id=status.id,
                            kind=status.kind,
                            display_name=status.display_name,
                            last_successful_import_at=status.last_successful_import_at,
                            coverage=SourceCoverageResponse.model_validate(
                                status.coverage
                            ),
                        )
                        for status in statuses
                    ]
                )
        finally:
            engine.dispose()

    return router
