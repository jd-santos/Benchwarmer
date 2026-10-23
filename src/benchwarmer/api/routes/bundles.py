"""Expose evidence bundles: revision-pinned excerpts with roles and rationale."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
import datetime as dt
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from benchwarmer.config import BenchwarmerSettings
from benchwarmer.db import create_engine, create_session_factory
from benchwarmer.evidence import (
    BundleDocument,
    BundleItem,
    BundleOrigin,
    BundleStatus,
    ObjectiveType,
    RunProvenance,
)
from benchwarmer.services.evidence_bundles import (
    BundleConflict,
    BundleDetail,
    BundleInvalid,
    BundleNotFound,
    create_bundle,
    find_bundle_by_request_id,
    get_bundle,
    list_bundle_memberships,
    list_bundles,
    update_bundle,
)


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ToolCallResponse(_Strict):
    """A tool call inside a cited event; arguments are the captured text, if any."""

    tool_call_id: str
    arguments: str | None


class ResolvedItemResponse(_Strict):
    """A bundle item and the captured evidence its reference resolves to."""

    item: BundleItem
    conversation_title: str | None
    conversation_is_latest: bool
    event_role: str
    event_kind: str
    occurred_at: str | None
    block_kind: str | None
    excerpt: str | None
    omitted_before: int | None
    tool_calls: list[ToolCallResponse]


class BundleRevisionResponse(_Strict):
    number: int
    origin: Literal["human", "generated"]
    producer: str
    provenance: RunProvenance | None
    created_at: dt.datetime


class BundleDetailResponse(_Strict):
    id: str
    revision: int
    latest_revision: int
    origin: Literal["human", "generated"]
    producer: str
    provenance: RunProvenance | None
    request_id: str | None
    created_at: dt.datetime
    updated_at: dt.datetime
    document: BundleDocument
    items: list[ResolvedItemResponse]
    revisions: list[BundleRevisionResponse]


class BundleMembershipResponse(_Strict):
    """One bundle that cites a conversation, and which of its events."""

    id: str
    revision: int
    summary: str
    status: BundleStatus
    origin: BundleOrigin
    run_id: str | None
    event_ids: list[str]


class BundleMembershipsResponse(_Strict):
    items: list[BundleMembershipResponse]


class BundleSummaryResponse(_Strict):
    """The latest revision of one bundle, with who produced that revision."""

    id: str
    revision: int
    summary: str
    objective: str
    objective_type: ObjectiveType
    goal: str
    status: BundleStatus
    origin: BundleOrigin
    producer: str
    run_id: str | None
    item_count: int
    conversation_ids: list[str]
    updated_at: dt.datetime


class BundlesResponse(_Strict):
    items: list[BundleSummaryResponse]


_Producer = Annotated[str, Field(min_length=1, max_length=255)]
_RequestId = Annotated[str, Field(min_length=1, max_length=255)]


class BundleCreateRequest(_Strict):
    """A new bundle; a generated one names the producer and run that proposed it.

    ``request_id`` makes creation idempotent: repeating a request with the
    same id returns the bundle it already created instead of a second one.
    """

    document: BundleDocument
    origin: BundleOrigin = "human"
    producer: _Producer = "web"
    provenance: RunProvenance | None = None
    request_id: _RequestId | None = None


class BundleUpdateRequest(_Strict):
    document: BundleDocument
    base_revision: Annotated[int, Field(ge=1)]
    origin: BundleOrigin = "human"
    producer: _Producer = "web"
    provenance: RunProvenance | None = None


def _detail_response(detail: BundleDetail) -> BundleDetailResponse:
    return BundleDetailResponse(
        id=detail.id,
        revision=detail.revision,
        latest_revision=detail.latest_revision,
        origin=detail.origin,  # type: ignore[arg-type]
        producer=detail.producer,
        provenance=detail.provenance,
        request_id=detail.request_id,
        created_at=detail.created_at,
        updated_at=detail.updated_at,
        document=detail.document,
        items=[
            ResolvedItemResponse(
                item=item.item,
                conversation_title=item.conversation_title,
                conversation_is_latest=item.conversation_is_latest,
                event_role=item.event_role,
                event_kind=item.event_kind,
                occurred_at=item.occurred_at,
                block_kind=item.block_kind,
                excerpt=item.excerpt,
                omitted_before=item.omitted_before,
                tool_calls=[
                    ToolCallResponse(
                        tool_call_id=call.tool_call_id, arguments=call.arguments
                    )
                    for call in item.tool_calls
                ],
            )
            for item in detail.items
        ],
        revisions=[
            BundleRevisionResponse(
                number=item.number,
                origin=item.origin,  # type: ignore[arg-type]
                producer=item.producer,
                provenance=item.provenance,
                created_at=item.created_at,
            )
            for item in detail.revisions
        ],
    )


def _invalid(error: BundleInvalid) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "detail": "Bundle evidence is invalid",
            "issues": [
                {
                    "item_index": item.item_index,
                    "code": item.code,
                    "message": item.message,
                }
                for item in error.issues
            ],
        },
    )


def create_bundles_router(settings: BenchwarmerSettings) -> APIRouter:
    """Create the evidence bundle routes for one resolved runtime configuration."""
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

    @router.get("/bundles", response_model=BundlesResponse)
    def get_bundles(
        conversation_id: Annotated[str | None, Query(max_length=255)] = None,
        origin: BundleOrigin | None = None,
        status: BundleStatus | None = None,
        run_id: Annotated[str | None, Query(max_length=255)] = None,
        objective_type: ObjectiveType | None = None,
    ) -> BundlesResponse:
        with session_scope() as session:
            summaries = list_bundles(
                session,
                conversation_id=conversation_id,
                origin=origin,
                status=status,
                run_id=run_id,
                objective_type=objective_type,
            )
            return BundlesResponse(
                items=[
                    BundleSummaryResponse(
                        id=item.id,
                        revision=item.revision,
                        summary=item.summary,
                        objective=item.objective,
                        objective_type=item.objective_type,  # type: ignore[arg-type]
                        goal=item.goal,
                        status=item.status,  # type: ignore[arg-type]
                        origin=item.origin,  # type: ignore[arg-type]
                        producer=item.producer,
                        run_id=item.run_id,
                        item_count=item.item_count,
                        conversation_ids=list(item.conversation_ids),
                        updated_at=item.updated_at,
                    )
                    for item in summaries
                ]
            )

    @router.get(
        "/conversations/{conversation_id}/bundles",
        response_model=BundleMembershipsResponse,
    )
    def get_conversation_bundles(conversation_id: str) -> BundleMembershipsResponse:
        with session_scope() as session:
            return BundleMembershipsResponse(
                items=[
                    BundleMembershipResponse(
                        id=item.id,
                        revision=item.revision,
                        summary=item.summary,
                        status=item.status,  # type: ignore[arg-type]
                        origin=item.origin,  # type: ignore[arg-type]
                        run_id=item.run_id,
                        event_ids=list(item.event_ids),
                    )
                    for item in list_bundle_memberships(session, conversation_id)
                ]
            )

    @router.post(
        "/bundles",
        status_code=201,
        response_model=BundleDetailResponse,
        responses={
            200: {"description": "A bundle this request id already created"},
            422: {"description": "Bundle evidence is invalid"},
        },
    )
    def post_bundle(
        request: BundleCreateRequest,
    ) -> BundleDetailResponse | JSONResponse:
        with session_scope() as session:
            if request.request_id is not None:
                existing = find_bundle_by_request_id(session, request.request_id)
                if existing is not None:
                    return JSONResponse(
                        status_code=200,
                        content=_detail_response(existing).model_dump(mode="json"),
                    )
            try:
                return _detail_response(
                    create_bundle(
                        session,
                        request.document,
                        origin=request.origin,
                        producer=request.producer,
                        provenance=request.provenance,
                        request_id=request.request_id,
                    )
                )
            except BundleInvalid as error:
                return _invalid(error)

    @router.get("/bundles/{bundle_id}", response_model=BundleDetailResponse)
    def get_bundle_detail(
        bundle_id: str, revision: Annotated[int | None, Query(ge=1)] = None
    ) -> BundleDetailResponse:
        with session_scope() as session:
            try:
                return _detail_response(
                    get_bundle(session, bundle_id, revision=revision)
                )
            except BundleNotFound:
                raise HTTPException(
                    status_code=404, detail="Bundle not found"
                ) from None

    @router.put(
        "/bundles/{bundle_id}",
        response_model=BundleDetailResponse,
        responses={
            409: {"description": "Bundle changed since it was loaded"},
            422: {"description": "Bundle evidence is invalid"},
        },
    )
    def put_bundle(
        bundle_id: str, request: BundleUpdateRequest
    ) -> BundleDetailResponse | JSONResponse:
        with session_scope() as session:
            try:
                return _detail_response(
                    update_bundle(
                        session,
                        bundle_id,
                        request.document,
                        base_revision=request.base_revision,
                        origin=request.origin,
                        producer=request.producer,
                        provenance=request.provenance,
                    )
                )
            except BundleNotFound:
                raise HTTPException(
                    status_code=404, detail="Bundle not found"
                ) from None
            except BundleConflict as error:
                return JSONResponse(
                    status_code=409,
                    content={
                        "detail": "Bundle changed since it was loaded",
                        "latest_revision": error.latest_revision,
                    },
                )
            except BundleInvalid as error:
                return _invalid(error)

    return router
