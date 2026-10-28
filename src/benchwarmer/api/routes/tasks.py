"""Expose task versions: a reviewed bundle prepared as a test, and its export."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
import datetime as dt
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from benchwarmer.anonymize import MAX_TERMS
from benchwarmer.config import BenchwarmerSettings
from benchwarmer.db import create_engine, create_session_factory
from benchwarmer.evidence import BundleDocument, ObjectiveType
from benchwarmer.services.case_export import (
    CaseExportNotApproved,
    CaseRecord,
    export_case,
)
from benchwarmer.services.scrub_terms import MAX_TERM_LENGTH, NAME_PATTERN
from benchwarmer.services.task_versions import (
    TaskConflict,
    TaskDetail,
    TaskDraft,
    TaskInvalid,
    TaskNotFound,
    TaskSplit,
    create_task,
    draft_task,
    get_task,
    list_tasks,
    update_task,
)
from benchwarmer.tasks import Partition, TaskDocument, TaskKind, TaskStatus


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class LeakageFlagResponse(_Strict):
    id: str
    code: str
    message: str
    event_id: str | None
    criterion_id: str | None
    item_index: int | None


class SplitEventResponse(_Strict):
    event_id: str
    role: str
    kind: str
    occurred_at: str | None
    preview: str | None
    cited_as: list[str]


class TaskSplitResponse(_Strict):
    """What the candidate sees and what only the judge sees."""

    conversation_id: str
    revision: str
    conversation_title: str | None
    candidate: list[SplitEventResponse]
    judge: list[SplitEventResponse]
    other_judge: list[SplitEventResponse]


class TaskVersionResponse(_Strict):
    number: int
    status: TaskStatus
    producer: str
    created_at: dt.datetime


class TaskDetailResponse(_Strict):
    id: str
    version: int
    latest_version: int
    producer: str
    created_at: dt.datetime
    updated_at: dt.datetime
    document: TaskDocument
    bundle: BundleDocument
    bundle_latest_revision: int
    split: TaskSplitResponse
    flags: list[LeakageFlagResponse]
    versions: list[TaskVersionResponse]


class TaskDraftResponse(_Strict):
    """A proposed starting document for a bundle; nothing is saved."""

    document: TaskDocument
    bundle: BundleDocument
    split: TaskSplitResponse
    flags: list[LeakageFlagResponse]


class TaskSummaryResponse(_Strict):
    id: str
    version: int
    status: TaskStatus
    kind: TaskKind
    summary: str
    objective: str
    objective_type: ObjectiveType
    family: str
    partition: Partition | None
    bundle_id: str
    bundle_revision: int
    criterion_count: int
    updated_at: dt.datetime


class TasksResponse(_Strict):
    items: list[TaskSummaryResponse]


_Producer = Annotated[str, Field(min_length=1, max_length=255)]


class TaskCreateRequest(_Strict):
    document: TaskDocument
    producer: _Producer = "web"


class TaskUpdateRequest(_Strict):
    document: TaskDocument
    base_version: Annotated[int, Field(ge=1)]
    producer: _Producer = "web"


class TermListRef(_Strict):
    """A stored term list by name; the latest version when none is given."""

    name: Annotated[str, Field(pattern=NAME_PATTERN)]
    version: Annotated[int, Field(ge=1)] | None = None


class CaseExportRequest(_Strict):
    """Export one approved version, scrubbing these terms besides the built-in kinds.

    ``terms`` and ``term_list`` combine; each side and the combination stay
    under the scrubber's cap.
    """

    version: Annotated[int, Field(ge=1)] | None = None
    terms: Annotated[
        list[Annotated[str, Field(min_length=1, max_length=MAX_TERM_LENGTH)]],
        Field(max_length=MAX_TERMS),
    ] = []
    term_list: TermListRef | None = None


def _split_response(split: TaskSplit) -> TaskSplitResponse:
    def events(items: Any) -> list[SplitEventResponse]:
        return [
            SplitEventResponse(
                event_id=item.event_id,
                role=item.role,
                kind=item.kind,
                occurred_at=item.occurred_at,
                preview=item.preview,
                cited_as=list(item.cited_as),
            )
            for item in items
        ]

    return TaskSplitResponse(
        conversation_id=split.conversation_id,
        revision=split.revision,
        conversation_title=split.conversation_title,
        candidate=events(split.candidate),
        judge=events(split.judge),
        other_judge=events(split.other_judge),
    )


def _flags_response(flags: Any) -> list[LeakageFlagResponse]:
    return [
        LeakageFlagResponse(
            id=flag.id,
            code=flag.code,
            message=flag.message,
            event_id=flag.event_id,
            criterion_id=flag.criterion_id,
            item_index=flag.item_index,
        )
        for flag in flags
    ]


def _detail_response(detail: TaskDetail) -> TaskDetailResponse:
    return TaskDetailResponse(
        id=detail.id,
        version=detail.version,
        latest_version=detail.latest_version,
        producer=detail.producer,
        created_at=detail.created_at,
        updated_at=detail.updated_at,
        document=detail.document,
        bundle=detail.bundle,
        bundle_latest_revision=detail.bundle_latest_revision,
        split=_split_response(detail.split),
        flags=_flags_response(detail.flags),
        versions=[
            TaskVersionResponse(
                number=item.number,
                status=item.status,  # type: ignore[arg-type]
                producer=item.producer,
                created_at=item.created_at,
            )
            for item in detail.versions
        ],
    )


def _draft_response(draft: TaskDraft) -> TaskDraftResponse:
    return TaskDraftResponse(
        document=draft.document,
        bundle=draft.bundle,
        split=_split_response(draft.split),
        flags=_flags_response(draft.flags),
    )


def _invalid(error: TaskInvalid) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "detail": "Task is invalid",
            "issues": [
                {
                    "code": item.code,
                    "message": item.message,
                    "criterion_id": item.criterion_id,
                }
                for item in error.issues
            ],
        },
    )


def create_tasks_router(settings: BenchwarmerSettings) -> APIRouter:
    """Create the task version routes for one resolved runtime configuration."""
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

    @router.get("/tasks", response_model=TasksResponse)
    def get_tasks(
        status: TaskStatus | None = None,
        bundle_id: Annotated[str | None, Query(max_length=255)] = None,
        family: Annotated[str | None, Query(max_length=255)] = None,
    ) -> TasksResponse:
        with session_scope() as session:
            return TasksResponse(
                items=[
                    TaskSummaryResponse(
                        id=item.id,
                        version=item.version,
                        status=item.status,  # type: ignore[arg-type]
                        kind=item.kind,  # type: ignore[arg-type]
                        summary=item.summary,
                        objective=item.objective,
                        objective_type=item.objective_type,  # type: ignore[arg-type]
                        family=item.family,
                        partition=item.partition,  # type: ignore[arg-type]
                        bundle_id=item.bundle_id,
                        bundle_revision=item.bundle_revision,
                        criterion_count=item.criterion_count,
                        updated_at=item.updated_at,
                    )
                    for item in list_tasks(
                        session, status=status, bundle_id=bundle_id, family=family
                    )
                ]
            )

    @router.get(
        "/bundles/{bundle_id}/task-draft",
        response_model=TaskDraftResponse,
        responses={422: {"description": "The bundle cannot seed a task"}},
    )
    def get_task_draft(
        bundle_id: str, revision: Annotated[int | None, Query(ge=1)] = None
    ) -> TaskDraftResponse | JSONResponse:
        with session_scope() as session:
            try:
                return _draft_response(
                    draft_task(session, bundle_id, bundle_revision=revision)
                )
            except TaskInvalid as error:
                if error.issues[0].code == "bundle_not_found":
                    raise HTTPException(
                        status_code=404, detail="Bundle not found"
                    ) from None
                return _invalid(error)

    @router.post(
        "/tasks",
        status_code=201,
        response_model=TaskDetailResponse,
        responses={422: {"description": "Task is invalid"}},
    )
    def post_task(request: TaskCreateRequest) -> TaskDetailResponse | JSONResponse:
        with session_scope() as session:
            try:
                return _detail_response(
                    create_task(session, request.document, producer=request.producer)
                )
            except TaskInvalid as error:
                return _invalid(error)

    @router.get("/tasks/{task_id}", response_model=TaskDetailResponse)
    def get_task_detail(
        task_id: str, version: Annotated[int | None, Query(ge=1)] = None
    ) -> TaskDetailResponse:
        with session_scope() as session:
            try:
                return _detail_response(get_task(session, task_id, version=version))
            except TaskNotFound:
                raise HTTPException(status_code=404, detail="Task not found") from None

    @router.put(
        "/tasks/{task_id}",
        response_model=TaskDetailResponse,
        responses={
            409: {"description": "Task changed since it was loaded"},
            422: {"description": "Task is invalid"},
        },
    )
    def put_task(
        task_id: str, request: TaskUpdateRequest
    ) -> TaskDetailResponse | JSONResponse:
        with session_scope() as session:
            try:
                return _detail_response(
                    update_task(
                        session,
                        task_id,
                        request.document,
                        base_version=request.base_version,
                        producer=request.producer,
                    )
                )
            except TaskNotFound:
                raise HTTPException(status_code=404, detail="Task not found") from None
            except TaskConflict as error:
                return JSONResponse(
                    status_code=409,
                    content={
                        "detail": "Task changed since it was loaded",
                        "latest_version": error.latest_version,
                    },
                )
            except TaskInvalid as error:
                return _invalid(error)

    @router.post(
        "/tasks/{task_id}/export",
        response_model=CaseRecord,
        responses={
            409: {"description": "Only an approved version exports"},
            422: {"description": "Task is invalid"},
        },
    )
    def post_task_export(
        task_id: str, request: CaseExportRequest
    ) -> CaseRecord | JSONResponse:
        with session_scope() as session:
            try:
                return export_case(
                    session,
                    task_id,
                    version=request.version,
                    terms=request.terms,
                    term_list_name=(
                        None if request.term_list is None else request.term_list.name
                    ),
                    term_list_version=(
                        None if request.term_list is None else request.term_list.version
                    ),
                )
            except TaskNotFound:
                raise HTTPException(status_code=404, detail="Task not found") from None
            except CaseExportNotApproved as error:
                return JSONResponse(
                    status_code=409,
                    content={
                        "detail": "Only an approved task version can be exported",
                        "status": error.status,
                    },
                )
            except TaskInvalid as error:
                return _invalid(error)

    return router
