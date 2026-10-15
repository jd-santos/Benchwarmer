"""Expose normalized conversations for browsing and keyword search."""

from __future__ import annotations

import datetime as dt
from typing import Annotated, Any, Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict

from benchwarmer.config import BenchwarmerSettings
from benchwarmer.db import create_engine, create_session_factory
from benchwarmer.services.conversation_library import (
    ConversationNotFound,
    ConversationSummary,
    get_conversation,
    list_conversations,
)

CoverageState = Literal["available", "partial", "unavailable", "unknown", "redacted"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class SourceRefResponse(_Strict):
    id: str
    kind: str
    display_name: str


class SearchHitResponse(_Strict):
    """A keyword match with the source anchor it came from."""

    event_id: str | None
    block_id: str | None
    field: str
    snippet: str


class ConversationSummaryResponse(_Strict):
    """List-level facts about one conversation's selected revision."""

    id: str
    source: SourceRefResponse
    native_id: str
    revision: str
    captured_at: dt.datetime
    title: str | None
    preview: str | None
    started_at: dt.datetime | None
    last_activity_at: dt.datetime | None
    event_count: int
    message_count: int
    branch_count: int
    relationship_counts: dict[str, int]
    coverage: dict[str, CoverageState]
    match_count: int
    matches: list[SearchHitResponse]


class ConversationsResponse(_Strict):
    """Stable envelope for one page of conversations."""

    items: list[ConversationSummaryResponse]
    total: int
    limit: int
    offset: int


class ContentBlockResponse(_Strict):
    id: str
    kind: Literal[
        "text", "reasoning", "tool_call", "tool_result", "attachment", "unknown"
    ]
    text: str | None
    tool_call_id: str | None
    artifact_id: str | None
    extensions: dict[str, Any]


class EventResponse(_Strict):
    """One captured event; timestamps are passed through as captured."""

    id: str
    native_id: str
    ordinal: int
    parent_id: str | None
    kind: Literal["message", "compaction", "configuration", "unknown"]
    role: Literal["system", "developer", "user", "assistant", "tool", "unknown"]
    occurred_at: str | None
    content: list[ContentBlockResponse]
    extensions: dict[str, Any]


class ArtifactResponse(_Strict):
    id: str
    kind: str
    media_type: str | None
    availability: CoverageState
    locator: str | None
    extensions: dict[str, Any]


class MetadataResponse(_Strict):
    name: str
    value: Any
    origin: Literal["imported", "calculated", "generated", "human"]
    producer: str
    producer_version: str | None
    input_revision: str
    extensions: dict[str, Any]


class RelationshipResponse(_Strict):
    """A captured relationship, resolved to a library conversation when present."""

    kind: Literal["branch", "continuation", "derived_from", "unknown"]
    target_source_kind: str
    target_source_scope_id: str
    target_native_id: str
    target_conversation_id: str | None
    extensions: dict[str, Any]


class IncomingRelationshipResponse(_Strict):
    kind: Literal["branch", "continuation", "derived_from", "unknown"]
    conversation_id: str


class BranchResponse(_Strict):
    """One root-to-leaf path; fork_event_id is where it last diverged."""

    id: str
    leaf_event_id: str
    event_ids: list[str]
    fork_event_id: str | None


class RevisionResponse(_Strict):
    revision: str
    captured_at: dt.datetime


class ConversationDetailResponse(_Strict):
    """A full normalized revision with derived navigation structure."""

    summary: ConversationSummaryResponse
    is_latest: bool
    revisions: list[RevisionResponse]
    events: list[EventResponse]
    artifacts: list[ArtifactResponse]
    metadata: list[MetadataResponse]
    relationships: list[RelationshipResponse]
    referenced_by: list[IncomingRelationshipResponse]
    branches: list[BranchResponse]


def _summary_response(summary: ConversationSummary) -> ConversationSummaryResponse:
    return ConversationSummaryResponse(
        id=summary.id,
        source=SourceRefResponse(
            id=summary.source.id,
            kind=summary.source.kind,
            display_name=summary.source.display_name,
        ),
        native_id=summary.native_id,
        revision=summary.revision,
        captured_at=summary.captured_at,
        title=summary.title,
        preview=summary.preview,
        started_at=summary.started_at,
        last_activity_at=summary.last_activity_at,
        event_count=summary.event_count,
        message_count=summary.message_count,
        branch_count=summary.branch_count,
        relationship_counts=summary.relationship_counts,
        coverage=summary.coverage,  # type: ignore[arg-type]
        match_count=summary.match_count,
        matches=[
            SearchHitResponse(
                event_id=hit.event_id,
                block_id=hit.block_id,
                field=hit.field,
                snippet=hit.snippet,
            )
            for hit in summary.matches
        ],
    )


def create_conversations_router(settings: BenchwarmerSettings) -> APIRouter:
    """Create the conversation routes for one resolved runtime configuration."""
    router = APIRouter()

    @router.get("/conversations", response_model=ConversationsResponse)
    def get_conversations(
        q: Annotated[str | None, Query(max_length=500)] = None,
        source_id: str | None = None,
        source_kind: str | None = None,
        limit: Annotated[int, Query(ge=1, le=200)] = 50,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> ConversationsResponse:
        engine = create_engine(settings)
        factory = create_session_factory(engine)
        try:
            with factory() as session:
                page = list_conversations(
                    session,
                    query=q,
                    source_id=source_id,
                    source_kind=source_kind,
                    limit=limit,
                    offset=offset,
                )
                return ConversationsResponse(
                    items=[_summary_response(item) for item in page.items],
                    total=page.total,
                    limit=page.limit,
                    offset=page.offset,
                )
        finally:
            engine.dispose()

    @router.get(
        "/conversations/{conversation_id}",
        response_model=ConversationDetailResponse,
    )
    def get_conversation_detail(
        conversation_id: str, revision: str | None = None
    ) -> ConversationDetailResponse:
        engine = create_engine(settings)
        factory = create_session_factory(engine)
        try:
            with factory() as session:
                try:
                    detail = get_conversation(
                        session, conversation_id, revision=revision
                    )
                except ConversationNotFound:
                    raise HTTPException(
                        status_code=404, detail="Conversation not found"
                    ) from None
                return ConversationDetailResponse(
                    summary=_summary_response(detail.summary),
                    is_latest=detail.is_latest,
                    revisions=[
                        RevisionResponse(
                            revision=item.revision, captured_at=item.captured_at
                        )
                        for item in detail.revisions
                    ],
                    events=[
                        EventResponse.model_validate(item) for item in detail.events
                    ],
                    artifacts=[
                        ArtifactResponse.model_validate(item)
                        for item in detail.artifacts
                    ],
                    metadata=[
                        MetadataResponse.model_validate(item)
                        for item in detail.metadata
                    ],
                    relationships=[
                        RelationshipResponse(
                            kind=item.kind,  # type: ignore[arg-type]
                            target_source_kind=item.target_source_kind,
                            target_source_scope_id=item.target_source_scope_id,
                            target_native_id=item.target_native_id,
                            target_conversation_id=item.target_conversation_id,
                            extensions=item.extensions,
                        )
                        for item in detail.relationships
                    ],
                    referenced_by=[
                        IncomingRelationshipResponse(
                            kind=item.kind,  # type: ignore[arg-type]
                            conversation_id=item.conversation_id,
                        )
                        for item in detail.referenced_by
                    ],
                    branches=[
                        BranchResponse(
                            id=item.id,
                            leaf_event_id=item.leaf_event_id,
                            event_ids=list(item.event_ids),
                            fork_event_id=item.fork_event_id,
                        )
                        for item in detail.branches
                    ],
                )
        finally:
            engine.dispose()

    return router
