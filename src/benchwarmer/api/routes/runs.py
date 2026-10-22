"""Expose records of hand-run harness workflows and their estimated usage."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
import datetime as dt
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from benchwarmer.config import BenchwarmerSettings
from benchwarmer.db import create_engine, create_session_factory
from benchwarmer.runs import HarnessRunRecord
from benchwarmer.services.harness_runs import (
    RunNotFound,
    get_run,
    list_runs,
    record_run,
)


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class RunSummaryResponse(_Strict):
    """One run at a glance; ``estimated_cost`` is a catalog estimate in USD."""

    run_id: str
    workflow: str
    provider: str
    model: str
    thinking_level: str | None
    base_url_override: str | None
    started_at: dt.datetime
    finished_at: dt.datetime
    input_count: int
    bundle_count: int
    total_tokens: int
    estimated_cost: float
    pricing_source: str


class RunsResponse(_Strict):
    items: list[RunSummaryResponse]


def create_runs_router(settings: BenchwarmerSettings) -> APIRouter:
    """Create the harness run routes for one resolved runtime configuration."""
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

    @router.get("/runs", response_model=RunsResponse)
    def get_runs(
        workflow: Annotated[str | None, Query(max_length=255)] = None,
    ) -> RunsResponse:
        with session_scope() as session:
            return RunsResponse(
                items=[
                    RunSummaryResponse(
                        run_id=item.run_id,
                        workflow=item.workflow,
                        provider=item.provider,
                        model=item.model,
                        thinking_level=item.thinking_level,
                        base_url_override=item.base_url_override,
                        started_at=item.started_at,
                        finished_at=item.finished_at,
                        input_count=item.input_count,
                        bundle_count=item.bundle_count,
                        total_tokens=item.total_tokens,
                        estimated_cost=item.estimated_cost,
                        pricing_source=item.pricing_source,
                    )
                    for item in list_runs(session, workflow=workflow)
                ]
            )

    @router.put(
        "/runs/{run_id}",
        response_model=HarnessRunRecord,
        responses={422: {"description": "The record does not match its contract"}},
    )
    def put_run(run_id: str, record: HarnessRunRecord) -> HarnessRunRecord:
        if record.run_id != run_id:
            raise HTTPException(
                status_code=422, detail="run_id in the path and body differ"
            )
        with session_scope() as session:
            return record_run(session, record)

    @router.get("/runs/{run_id}", response_model=HarnessRunRecord)
    def get_run_record(run_id: str) -> HarnessRunRecord:
        with session_scope() as session:
            try:
                return get_run(session, run_id)
            except RunNotFound:
                raise HTTPException(status_code=404, detail="Run not found") from None

    return router
