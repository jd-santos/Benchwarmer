"""Expose persisted source import status and host-local file imports."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
import datetime as dt
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from benchwarmer.config import BenchwarmerSettings
from benchwarmer.db import create_engine, create_session_factory
from benchwarmer.services.imports import (
    IMPORTABLE_KINDS,
    ImportRequestError,
    SourceNotFound,
    list_import_batches,
    run_file_import,
)
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


class ImportConfigResponse(BaseModel):
    """Where this host may import files from, and which source kinds accept them."""

    model_config = ConfigDict(extra="forbid", strict=True)

    roots: list[str]
    kinds: list[str]


class ImportBatchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    id: str
    outcome: str
    started_at: dt.datetime
    completed_at: dt.datetime
    error_summary: str | None


class ImportBatchesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    items: list[ImportBatchResponse]


class ImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    path: str = Field(min_length=1, max_length=4096)


class ImportRunResponse(BaseModel):
    """What one import did. ``unchanged`` means these exact files were imported before."""

    model_config = ConfigDict(extra="forbid", strict=True)

    batch_id: str
    outcome: Literal["succeeded", "failed", "unchanged"]
    conversations: int
    revisions: int
    snapshots: int
    error_summary: str | None


def create_sources_router(settings: BenchwarmerSettings) -> APIRouter:
    """Create the source routes for one resolved runtime configuration."""
    router = APIRouter()

    @contextmanager
    def session_scope() -> Iterator[Session]:
        engine = create_engine(settings)
        factory: Callable[[], Session] = create_session_factory(engine)
        try:
            with factory() as session:
                yield session
        finally:
            engine.dispose()

    @router.get("/imports/config", response_model=ImportConfigResponse)
    def get_import_config() -> ImportConfigResponse:
        return ImportConfigResponse(
            roots=[str(root) for root in settings.import_roots],
            kinds=list(IMPORTABLE_KINDS),
        )

    @router.get("/sources/{source_id}/imports", response_model=ImportBatchesResponse)
    def get_source_imports(source_id: str) -> ImportBatchesResponse:
        with session_scope() as session:
            try:
                batches = list_import_batches(session, source_id)
            except SourceNotFound:
                raise HTTPException(
                    status_code=404, detail="Source not found"
                ) from None
            return ImportBatchesResponse(
                items=[
                    ImportBatchResponse(
                        id=batch.id,
                        outcome=batch.outcome,
                        started_at=batch.started_at,
                        completed_at=batch.completed_at,
                        error_summary=batch.error_summary,
                    )
                    for batch in batches
                ]
            )

    @router.post(
        "/sources/{source_id}/imports",
        response_model=ImportRunResponse,
        responses={
            404: {"description": "Unknown source"},
            422: {"description": "The path or source kind cannot be imported"},
        },
    )
    def post_source_import(source_id: str, request: ImportRequest) -> ImportRunResponse:
        with session_scope() as session:
            try:
                run = run_file_import(
                    settings, session, source_id=source_id, raw_path=request.path
                )
            except SourceNotFound:
                raise HTTPException(
                    status_code=404, detail="Source not found"
                ) from None
            except ImportRequestError as error:
                raise HTTPException(status_code=422, detail=str(error)) from None
            return ImportRunResponse(
                batch_id=run.batch_id,
                outcome=run.outcome,
                conversations=run.conversations,
                revisions=run.revisions,
                snapshots=run.snapshots,
                error_summary=run.error_summary,
            )

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
