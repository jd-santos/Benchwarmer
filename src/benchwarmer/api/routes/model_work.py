"""Preview, approve, and run bounded model work from the application."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
import datetime as dt
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from benchwarmer.config import BenchwarmerSettings
from benchwarmer.db import create_engine, create_session_factory
from benchwarmer.services.model_work_plans import (
    MAX_PLAN_INPUTS,
    THINKING_LEVELS,
    WORKFLOWS,
    PlanConflict,
    PlanNotFound,
    PlanRequestError,
    PlanRunner,
    PlanView,
    create_plan,
    get_plan,
    list_plans,
)


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ModelWorkConfigResponse(_Strict):
    """Whether this application can start harness runs, and which workflows."""

    can_run: bool
    workflows: list[str]
    thinking_levels: list[str]
    max_inputs: int


class PlanModelRequest(_Strict):
    provider: str = Field(min_length=1, max_length=255)
    model_id: str = Field(min_length=1, max_length=255)
    thinking_level: str | None = None


class PlanRequest(_Strict):
    workflow: str = Field(min_length=1, max_length=255)
    conversation_ids: list[str] = Field(min_length=1, max_length=MAX_PLAN_INPUTS)
    model: PlanModelRequest
    instructions: str | None = Field(default=None, max_length=4000)


class ApprovalRequest(_Strict):
    digest: str = Field(min_length=64, max_length=64)


class PlanInputResponse(_Strict):
    conversation_id: str
    revision: str
    title: str | None


class PlanModelResponse(_Strict):
    provider: str
    model_id: str
    thinking_level: str | None


class PlanResponse(_Strict):
    """A frozen plan. ``estimated_cost`` is null: nothing is priced before the run reports usage."""

    id: str
    workflow: str
    status: Literal[
        "proposed",
        "approved",
        "running",
        "finished",
        "failed",
        "cancelled",
        "interrupted",
    ]
    digest: str
    inputs: list[PlanInputResponse]
    model: PlanModelResponse
    max_inputs: int
    instructions: str | None
    estimated_cost: None
    run_id: str | None
    exit_code: int | None
    error_summary: str | None
    created_at: dt.datetime
    approved_at: dt.datetime | None
    started_at: dt.datetime | None
    finished_at: dt.datetime | None


class PlansResponse(_Strict):
    items: list[PlanResponse]


def _response(plan: PlanView) -> PlanResponse:
    return PlanResponse(
        id=plan.id,
        workflow=plan.workflow,
        status=plan.status,  # type: ignore[arg-type]
        digest=plan.digest,
        inputs=[
            PlanInputResponse(
                conversation_id=item.conversation_id,
                revision=item.revision,
                title=item.title,
            )
            for item in plan.inputs
        ],
        model=PlanModelResponse(
            provider=plan.model.provider,
            model_id=plan.model.model_id,
            thinking_level=plan.model.thinking_level,
        ),
        max_inputs=plan.max_inputs,
        instructions=plan.instructions,
        estimated_cost=None,
        run_id=plan.run_id,
        exit_code=plan.exit_code,
        error_summary=plan.error_summary,
        created_at=plan.created_at,
        approved_at=plan.approved_at,
        started_at=plan.started_at,
        finished_at=plan.finished_at,
    )


def create_model_work_router(
    settings: BenchwarmerSettings, runner: PlanRunner
) -> APIRouter:
    """Create the model-work routes for one resolved runtime configuration."""
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

    @router.get("/model-work/config", response_model=ModelWorkConfigResponse)
    def get_config() -> ModelWorkConfigResponse:
        return ModelWorkConfigResponse(
            can_run=settings.harness_dir is not None
            and (settings.harness_dir / "package.json").is_file(),
            workflows=list(WORKFLOWS),
            thinking_levels=list(THINKING_LEVELS),
            max_inputs=MAX_PLAN_INPUTS,
        )

    @router.get("/model-work/plans", response_model=PlansResponse)
    def get_plans() -> PlansResponse:
        with session_scope() as session:
            return PlansResponse(
                items=[_response(plan) for plan in list_plans(session)]
            )

    @router.post(
        "/model-work/plans",
        response_model=PlanResponse,
        status_code=201,
        responses={422: {"description": "The plan names something that cannot run"}},
    )
    def post_plan(request: PlanRequest) -> PlanResponse:
        with session_scope() as session:
            try:
                plan = create_plan(
                    session,
                    workflow=request.workflow,
                    conversation_ids=request.conversation_ids,
                    provider=request.model.provider,
                    model_id=request.model.model_id,
                    thinking_level=request.model.thinking_level,
                    instructions=request.instructions,
                )
            except PlanRequestError as error:
                raise HTTPException(status_code=422, detail=str(error)) from None
            return _response(plan)

    @router.get("/model-work/plans/{plan_id}", response_model=PlanResponse)
    def get_one(plan_id: str) -> PlanResponse:
        with session_scope() as session:
            try:
                return _response(get_plan(session, plan_id))
            except PlanNotFound:
                raise HTTPException(status_code=404, detail="Plan not found") from None

    @router.post(
        "/model-work/plans/{plan_id}/approve",
        response_model=PlanResponse,
        responses={
            404: {"description": "Unknown plan"},
            409: {
                "description": "The digest does not match or the plan is not proposed"
            },
            422: {"description": "This application cannot start harness runs"},
        },
    )
    def approve(
        plan_id: str, approval: ApprovalRequest, request: Request
    ) -> PlanResponse:
        api_base_url = str(request.base_url).rstrip("/")
        with session_scope() as session:
            try:
                return _response(
                    runner.approve_and_start(
                        session, plan_id, approval.digest, api_base_url
                    )
                )
            except PlanNotFound:
                raise HTTPException(status_code=404, detail="Plan not found") from None
            except PlanConflict as error:
                raise HTTPException(status_code=409, detail=str(error)) from None
            except PlanRequestError as error:
                raise HTTPException(status_code=422, detail=str(error)) from None

    @router.post(
        "/model-work/plans/{plan_id}/cancel",
        response_model=PlanResponse,
        responses={
            404: {"description": "Unknown plan"},
            409: {"description": "Not running"},
        },
    )
    def cancel(plan_id: str) -> PlanResponse:
        with session_scope() as session:
            try:
                return _response(runner.cancel(session, plan_id))
            except PlanNotFound:
                raise HTTPException(status_code=404, detail="Plan not found") from None
            except PlanConflict as error:
                raise HTTPException(status_code=409, detail=str(error)) from None

    return router
