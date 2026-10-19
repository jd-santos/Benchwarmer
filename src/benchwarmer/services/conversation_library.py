"""Read normalized conversations for browsing and keyword search.

Every read uses retained normalized revisions. Nothing here derives titles,
summaries, or other generated content; absent source facts stay absent.
"""

from __future__ import annotations

from dataclasses import dataclass
import datetime as dt
from typing import Any, cast

from sqlalchemy import String, cast as sql_cast, func, select
from sqlalchemy.orm import Session

from benchwarmer.models.source import ConversationRevision, Source

SEARCHABLE_BLOCK_KINDS = frozenset({"text", "reasoning", "tool_call", "tool_result"})
MAX_MATCHES_PER_CONVERSATION = 3
SNIPPET_RADIUS = 60
PREVIEW_LENGTH = 160


class ConversationNotFound(LookupError):
    """Raised when a conversation or a requested revision does not exist."""


@dataclass(frozen=True)
class SourceRef:
    """The configured source that captured a conversation."""

    id: str
    kind: str
    display_name: str


@dataclass(frozen=True)
class SearchHit:
    """One keyword match anchored to its source event and block."""

    event_id: str | None
    block_id: str | None
    field: str
    snippet: str


@dataclass(frozen=True)
class ConversationSummary:
    """List-level facts about the latest retained revision of a conversation."""

    id: str
    source: SourceRef
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
    coverage: dict[str, str]
    match_count: int
    matches: tuple[SearchHit, ...]


@dataclass(frozen=True)
class ConversationPage:
    """One bounded page of conversation summaries."""

    items: tuple[ConversationSummary, ...]
    total: int
    limit: int
    offset: int


@dataclass(frozen=True)
class Branch:
    """One root-to-leaf path through a conversation's event tree.

    ``is_original`` marks the path that follows the earliest-captured child at
    every fork. ``divergent_event_id`` is the first event after the last fork.
    ``models`` lists models the source recorded for events on this path; it is
    empty when the source captured none. Every path here is captured history;
    Benchwarmer trials will be recorded separately.
    """

    id: str
    leaf_event_id: str
    event_ids: tuple[str, ...]
    fork_event_id: str | None
    divergent_event_id: str | None
    is_original: bool
    models: tuple[str, ...]


@dataclass(frozen=True)
class RevisionRef:
    """One retained normalized revision of a conversation."""

    revision: str
    captured_at: dt.datetime


@dataclass(frozen=True)
class ResolvedRelationship:
    """A captured relationship and the library conversation it names, if any."""

    kind: str
    target_source_kind: str
    target_source_scope_id: str
    target_native_id: str
    target_conversation_id: str | None
    extensions: dict[str, Any]


@dataclass(frozen=True)
class IncomingRelationship:
    """Another conversation whose captured relationship names this one."""

    kind: str
    conversation_id: str


@dataclass(frozen=True)
class ConversationDetail:
    """A full normalized revision with derived navigation structure."""

    summary: ConversationSummary
    is_latest: bool
    revisions: tuple[RevisionRef, ...]
    events: tuple[dict[str, Any], ...]
    artifacts: tuple[dict[str, Any], ...]
    metadata: tuple[dict[str, Any], ...]
    relationships: tuple[ResolvedRelationship, ...]
    referenced_by: tuple[IncomingRelationship, ...]
    branches: tuple[Branch, ...]


def _latest_revisions(session: Session) -> list[tuple[ConversationRevision, Source]]:
    ranked = select(
        ConversationRevision.id,
        func.row_number()
        .over(
            partition_by=(
                ConversationRevision.source_id,
                ConversationRevision.native_id,
            ),
            order_by=(
                ConversationRevision.captured_at.desc(),
                ConversationRevision.created_at.desc(),
                ConversationRevision.id.desc(),
            ),
        )
        .label("rank"),
    ).subquery()
    rows = session.execute(
        select(ConversationRevision, Source)
        .join(ranked, ranked.c.id == ConversationRevision.id)
        .join(Source, Source.id == ConversationRevision.source_id)
        .where(ranked.c.rank == 1)
    ).all()
    return [(row[0], row[1]) for row in rows]


def _events(document: dict[str, Any]) -> list[dict[str, Any]]:
    return cast(list[dict[str, Any]], document["events"])


def _title(document: dict[str, Any]) -> str | None:
    for entry in document["metadata"]:
        if entry["name"] == "title" and isinstance(entry["value"], str):
            value = entry["value"].strip()
            if value:
                return value
    return None


def _preview(events: list[dict[str, Any]]) -> str | None:
    for event in events:
        if event["kind"] != "message" or event["role"] != "user":
            continue
        for block in event["content"]:
            if block["kind"] == "text" and isinstance(block["text"], str):
                text = " ".join(block["text"].split())
                if text:
                    return text[:PREVIEW_LENGTH]
    return None


def _event_models(document: dict[str, Any] | None) -> dict[str, str]:
    """Map native event ids to models recorded in imported usage observations."""
    models: dict[str, str] = {}
    if document is None:
        return models
    for entry in document["metadata"]:
        if entry["name"] != "usage_observations" or not isinstance(
            entry["value"], list
        ):
            continue
        for observation in entry["value"]:
            if not isinstance(observation, dict):
                continue
            native_id, model = observation.get("entry_id"), observation.get("model")
            if isinstance(native_id, str) and isinstance(model, str) and model:
                models[native_id] = model
    return models


def _branches(
    events: list[dict[str, Any]], document: dict[str, Any] | None = None
) -> tuple[Branch, ...]:
    """Return root-to-leaf paths in leaf order; validation guarantees a forest."""
    by_id = {event["id"]: event for event in events}
    children: dict[str, list[dict[str, Any]]] = {event["id"]: [] for event in events}
    for event in events:
        if event["parent_id"] is not None:
            children[event["parent_id"]].append(event)
    first_child = {
        parent: min(items, key=lambda item: item["ordinal"])["id"]
        for parent, items in children.items()
        if items
    }
    event_models = _event_models(document)
    branches: list[Branch] = []
    for event in events:
        if children[event["id"]]:
            continue
        path: list[str] = []
        fork: str | None = None
        divergent: str | None = None
        original = True
        current: dict[str, Any] | None = event
        while current is not None:
            path.append(current["id"])
            parent_id = current["parent_id"]
            if parent_id is not None and len(children[parent_id]) > 1:
                if fork is None:
                    fork, divergent = parent_id, current["id"]
                if first_child[parent_id] != current["id"]:
                    original = False
            current = by_id[parent_id] if parent_id is not None else None
        path.reverse()
        models = tuple(
            dict.fromkeys(
                event_models[by_id[item]["native_id"]]
                for item in path
                if by_id[item]["native_id"] in event_models
            )
        )
        branches.append(
            Branch(
                id=event["id"],
                leaf_event_id=event["id"],
                event_ids=tuple(path),
                fork_event_id=fork,
                divergent_event_id=divergent,
                is_original=original,
                models=models,
            )
        )
    return tuple(branches)


def _parse_timestamp(value: str) -> dt.datetime:
    # The conversation contract guarantees timezone-qualified ISO timestamps.
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(dt.UTC)


def _snippet(text: str, start: int, length: int) -> str:
    left = max(0, start - SNIPPET_RADIUS)
    right = min(len(text), start + length + SNIPPET_RADIUS)
    snippet = " ".join(text[left:right].split())
    if left > 0:
        snippet = "…" + snippet
    if right < len(text):
        snippet = snippet + "…"
    return snippet


def _search(
    document: dict[str, Any], title: str | None, needle: str
) -> tuple[int, tuple[SearchHit, ...]]:
    count = 0
    hits: list[SearchHit] = []

    def scan(text: str, field: str, event_id: str | None, block_id: str | None) -> None:
        nonlocal count
        folded = text.casefold()
        position = folded.find(needle)
        while position != -1:
            count += 1
            if len(hits) < MAX_MATCHES_PER_CONVERSATION:
                hits.append(
                    SearchHit(
                        event_id=event_id,
                        block_id=block_id,
                        field=field,
                        snippet=_snippet(text, position, len(needle)),
                    )
                )
            position = folded.find(needle, position + len(needle))

    if title is not None:
        scan(title, "title", None, None)
    for event in _events(document):
        for block in event["content"]:
            text = block["text"]
            if block["kind"] in SEARCHABLE_BLOCK_KINDS and isinstance(text, str):
                scan(text, block["kind"], event["id"], block["id"])
    return count, tuple(hits)


def _summary(
    revision: ConversationRevision,
    source: Source,
    *,
    needle: str | None = None,
) -> ConversationSummary:
    document = revision.document
    events = _events(document)
    title = _title(document)
    timestamps = sorted(
        _parse_timestamp(event["occurred_at"])
        for event in events
        if event["occurred_at"] is not None
    )
    relationship_counts: dict[str, int] = {}
    for relationship in document["relationships"]:
        kind = relationship["kind"]
        relationship_counts[kind] = relationship_counts.get(kind, 0) + 1
    match_count, matches = (
        _search(document, title, needle) if needle is not None else (0, ())
    )
    return ConversationSummary(
        id=document["id"],
        source=SourceRef(
            id=source.id, kind=source.kind, display_name=source.display_name
        ),
        native_id=revision.native_id,
        revision=revision.revision,
        captured_at=revision.captured_at,
        title=title,
        preview=_preview(events),
        started_at=timestamps[0] if timestamps else None,
        last_activity_at=timestamps[-1] if timestamps else None,
        event_count=len(events),
        message_count=sum(1 for event in events if event["kind"] == "message"),
        branch_count=len(_branches(events)),
        relationship_counts=relationship_counts,
        coverage=dict(document["coverage"]),
        match_count=match_count,
        matches=matches,
    )


def _activity_key(summary: ConversationSummary) -> tuple[bool, dt.datetime, str]:
    # Unknown activity sorts after known activity rather than borrowing the
    # capture time, which would misstate when the work happened.
    known = summary.last_activity_at is not None
    return (known, summary.last_activity_at or summary.captured_at, summary.id)


def list_conversations(
    session: Session,
    *,
    query: str | None = None,
    source_id: str | None = None,
    source_kind: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> ConversationPage:
    """List latest revisions, most recent activity first, optionally searched."""
    needle = query.strip().casefold() if query is not None else None
    if needle == "":
        needle = None
    summaries: list[ConversationSummary] = []
    for revision, source in _latest_revisions(session):
        if source_id is not None and source.id != source_id:
            continue
        if source_kind is not None and source.kind != source_kind:
            continue
        summary = _summary(revision, source, needle=needle)
        if needle is not None and summary.match_count == 0:
            continue
        summaries.append(summary)
    summaries.sort(key=_activity_key, reverse=True)
    return ConversationPage(
        items=tuple(summaries[offset : offset + limit]),
        total=len(summaries),
        limit=limit,
        offset=offset,
    )


def _conversation_ids_by_target(
    session: Session, targets: set[tuple[str, str, str]]
) -> dict[tuple[str, str, str], str]:
    resolved: dict[tuple[str, str, str], str] = {}
    for kind, scope_id, native_id in targets:
        row = session.execute(
            select(ConversationRevision.document)
            .join(Source, Source.id == ConversationRevision.source_id)
            .where(
                Source.kind == kind,
                Source.scope_id == scope_id,
                ConversationRevision.native_id == native_id,
            )
            .limit(1)
        ).first()
        if row is not None:
            resolved[(kind, scope_id, native_id)] = row[0]["id"]
    return resolved


def _referenced_by(
    session: Session, source: Source, native_id: str
) -> tuple[IncomingRelationship, ...]:
    """Find latest revisions whose relationships name this conversation."""
    # The text prefilter only narrows candidates; matches are confirmed below.
    needle = f'"{native_id}"'
    candidates = session.execute(
        select(ConversationRevision.id).where(
            sql_cast(ConversationRevision.document, String).contains(needle)
        )
    ).all()
    candidate_ids = {row[0] for row in candidates}
    incoming: list[IncomingRelationship] = []
    for revision, _ in _latest_revisions(session):
        if revision.id not in candidate_ids:
            continue
        for relationship in revision.document["relationships"]:
            if (
                relationship["target_source_kind"] == source.kind
                and relationship["target_source_scope_id"] == source.scope_id
                and relationship["target_native_id"] == native_id
            ):
                incoming.append(
                    IncomingRelationship(
                        kind=relationship["kind"],
                        conversation_id=revision.document["id"],
                    )
                )
    incoming.sort(key=lambda item: (item.kind, item.conversation_id))
    return tuple(incoming)


def get_conversation(
    session: Session, conversation_id: str, *, revision: str | None = None
) -> ConversationDetail:
    """Return the latest or a requested revision of one conversation."""
    latest = {row[0].document["id"]: row for row in _latest_revisions(session)}.get(
        conversation_id
    )
    if latest is None:
        raise ConversationNotFound(conversation_id)
    latest_revision, source = latest
    history = session.execute(
        select(ConversationRevision)
        .where(
            ConversationRevision.source_id == latest_revision.source_id,
            ConversationRevision.native_id == latest_revision.native_id,
        )
        .order_by(
            ConversationRevision.captured_at.desc(),
            ConversationRevision.created_at.desc(),
            ConversationRevision.id.desc(),
        )
    ).scalars()
    history_rows = list(history)
    selected = latest_revision
    if revision is not None:
        matching = [row for row in history_rows if row.revision == revision]
        if not matching:
            raise ConversationNotFound(conversation_id)
        selected = matching[0]

    document = selected.document
    events = _events(document)
    relationships = document["relationships"]
    targets = {
        (
            item["target_source_kind"],
            item["target_source_scope_id"],
            item["target_native_id"],
        )
        for item in relationships
    }
    resolved = _conversation_ids_by_target(session, targets)
    return ConversationDetail(
        summary=_summary(selected, source),
        is_latest=selected.id == latest_revision.id,
        revisions=tuple(
            RevisionRef(revision=row.revision, captured_at=row.captured_at)
            for row in history_rows
        ),
        events=tuple(events),
        artifacts=tuple(document["artifacts"]),
        metadata=tuple(document["metadata"]),
        relationships=tuple(
            ResolvedRelationship(
                kind=item["kind"],
                target_source_kind=item["target_source_kind"],
                target_source_scope_id=item["target_source_scope_id"],
                target_native_id=item["target_native_id"],
                target_conversation_id=resolved.get(
                    (
                        item["target_source_kind"],
                        item["target_source_scope_id"],
                        item["target_native_id"],
                    )
                ),
                extensions=item["extensions"],
            )
            for item in relationships
        ),
        referenced_by=_referenced_by(session, source, latest_revision.native_id),
        branches=_branches(events, document),
    )
