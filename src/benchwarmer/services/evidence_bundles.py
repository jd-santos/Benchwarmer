"""Create, revise, and resolve evidence bundles against pinned conversations.

Bundles cite immutable conversation revisions, so a reference that resolved when
it was saved keeps resolving. Saving never changes imported history.
"""

from __future__ import annotations

from dataclasses import dataclass
import datetime as dt
from typing import Any
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from benchwarmer.evidence import BundleDocument, BundleItem, EvidenceRef, RunProvenance
from benchwarmer.models.evidence_bundle import EvidenceBundle, EvidenceBundleRevision
from benchwarmer.models.source import ConversationRevision, utc_now

_TITLE = "title"


class BundleNotFound(LookupError):
    """Raised when a bundle or a requested bundle revision does not exist."""


class BundleConflict(RuntimeError):
    """Raised when a save is based on a revision that is no longer the latest."""

    def __init__(self, latest_revision: int) -> None:
        super().__init__("bundle changed since it was loaded")
        self.latest_revision = latest_revision


@dataclass(frozen=True)
class EvidenceIssue:
    """Why one bundle item, or the bundle as a whole, cannot be saved."""

    item_index: int | None
    code: str
    message: str


class BundleInvalid(ValueError):
    """Raised when bundle evidence does not resolve or is incoherent."""

    def __init__(self, issues: tuple[EvidenceIssue, ...]) -> None:
        super().__init__("bundle evidence is invalid")
        self.issues = issues


@dataclass(frozen=True)
class ResolvedItem:
    """A bundle item with the captured evidence it cites."""

    item: BundleItem
    conversation_title: str | None
    conversation_is_latest: bool
    event_role: str
    event_kind: str
    occurred_at: str | None
    block_kind: str | None
    excerpt: str | None
    omitted_before: int | None


@dataclass(frozen=True)
class BundleRevisionRef:
    number: int
    origin: str
    producer: str
    provenance: RunProvenance | None
    created_at: dt.datetime


@dataclass(frozen=True)
class BundleDetail:
    id: str
    revision: int
    latest_revision: int
    origin: str
    producer: str
    provenance: RunProvenance | None
    request_id: str | None
    created_at: dt.datetime
    updated_at: dt.datetime
    document: BundleDocument
    items: tuple[ResolvedItem, ...]
    revisions: tuple[BundleRevisionRef, ...]


@dataclass(frozen=True)
class BundleSummary:
    id: str
    revision: int
    summary: str
    objective: str
    goal: str
    status: str
    origin: str
    producer: str
    run_id: str | None
    item_count: int
    conversation_ids: tuple[str, ...]
    updated_at: dt.datetime


@dataclass(frozen=True)
class _Conversation:
    row: ConversationRevision
    is_latest: bool
    events: dict[str, dict[str, Any]]
    title: str | None

    @property
    def document(self) -> dict[str, Any]:
        return self.row.document

    def ancestors(self, event_id: str) -> list[str]:
        """Return the root-to-event path, inclusive."""
        path: list[str] = []
        current: str | None = event_id
        while current is not None:
            path.append(current)
            current = self.events[current]["parent_id"]
        path.reverse()
        return path


def _title(document: dict[str, Any]) -> str | None:
    for entry in document["metadata"]:
        if entry["name"] == _TITLE and isinstance(entry["value"], str):
            value = entry["value"].strip()
            if value:
                return value
    return None


def _load_conversations(
    session: Session, refs: list[EvidenceRef]
) -> dict[tuple[str, str], _Conversation]:
    wanted = {(ref.conversation_id, ref.revision) for ref in refs}
    rows = session.execute(
        select(ConversationRevision).where(
            ConversationRevision.revision.in_({revision for _, revision in wanted})
        )
    ).scalars()
    loaded: dict[tuple[str, str], _Conversation] = {}
    for row in rows:
        key = (row.document["id"], row.revision)
        if key not in wanted:
            continue
        latest = session.execute(
            select(ConversationRevision.id)
            .where(
                ConversationRevision.source_id == row.source_id,
                ConversationRevision.native_id == row.native_id,
            )
            .order_by(
                ConversationRevision.captured_at.desc(),
                ConversationRevision.created_at.desc(),
                ConversationRevision.id.desc(),
            )
            .limit(1)
        ).scalar_one()
        loaded[key] = _Conversation(
            row=row,
            is_latest=latest == row.id,
            events={event["id"]: event for event in row.document["events"]},
            title=_title(row.document),
        )
    return loaded


def _source_key(document: dict[str, Any]) -> tuple[str, str, str]:
    source = document["source"]
    return (source["kind"], source["scope_id"], source["native_id"])


def _validate(
    document: BundleDocument, conversations: dict[tuple[str, str], _Conversation]
) -> tuple[EvidenceIssue, ...]:
    issues: list[EvidenceIssue] = []
    revisions: dict[str, str] = {}
    by_conversation: dict[str, list[tuple[int, str]]] = {}
    for index, item in enumerate(document.items):
        ref = item.ref
        pinned = revisions.setdefault(ref.conversation_id, ref.revision)
        if pinned != ref.revision:
            issues.append(
                EvidenceIssue(
                    index,
                    "mixed_revisions",
                    "Items from one conversation must cite the same revision.",
                )
            )
            continue
        conversation = conversations.get((ref.conversation_id, ref.revision))
        if conversation is None:
            issues.append(
                EvidenceIssue(
                    index,
                    "conversation_not_found",
                    "The cited conversation revision is not in the library.",
                )
            )
            continue
        event = conversation.events.get(ref.event_id)
        if event is None:
            issues.append(
                EvidenceIssue(
                    index, "event_not_found", "The cited event is not in that revision."
                )
            )
            continue
        by_conversation.setdefault(ref.conversation_id, []).append(
            (index, ref.event_id)
        )
        if ref.block_id is None:
            continue
        block = next(
            (part for part in event["content"] if part["id"] == ref.block_id), None
        )
        if block is None:
            issues.append(
                EvidenceIssue(
                    index, "block_not_found", "The cited block is not in that event."
                )
            )
            continue
        if ref.text_start is None:
            continue
        text = block["text"]
        if not isinstance(text, str):
            issues.append(
                EvidenceIssue(
                    index,
                    "text_not_captured",
                    "A text range cannot cite a block whose text was not captured.",
                )
            )
        elif ref.text_end > len(text):  # type: ignore[operator]
            issues.append(
                EvidenceIssue(
                    index,
                    "range_out_of_bounds",
                    "The text range extends past the end of the block.",
                )
            )

    for conversation_id, cited in by_conversation.items():
        conversation = conversations[(conversation_id, revisions[conversation_id])]
        paths = {event_id: conversation.ancestors(event_id) for _, event_id in cited}
        deepest = max(paths.values(), key=len)
        on_path = set(deepest)
        for index, event_id in cited:
            if event_id not in on_path:
                issues.append(
                    EvidenceIssue(
                        index,
                        "sibling_branches",
                        "Items from one conversation must lie on a single path; "
                        "this item is on a different branch.",
                    )
                )

    if len(by_conversation) > 1 and not issues:
        cited_conversations = [
            conversations[(conversation_id, revisions[conversation_id])]
            for conversation_id in by_conversation
        ]
        keys = {
            _source_key(item.document): item.document["id"]
            for item in cited_conversations
        }
        parent = {
            item.document["id"]: item.document["id"] for item in cited_conversations
        }

        def root(node: str) -> str:
            while parent[node] != node:
                node = parent[node]
            return node

        for item in cited_conversations:
            for relationship in item.document["relationships"]:
                target = keys.get(
                    (
                        relationship["target_source_kind"],
                        relationship["target_source_scope_id"],
                        relationship["target_native_id"],
                    )
                )
                if target is not None:
                    parent[root(item.document["id"])] = root(target)
        if len({root(node) for node in parent}) > 1:
            issues.append(
                EvidenceIssue(
                    None,
                    "unrelated_conversations",
                    "Items cite conversations with no captured relationship "
                    "(continuation, branch, or derivation) connecting them.",
                )
            )
    return tuple(issues)


def _excerpt(event: dict[str, Any], ref: EvidenceRef) -> tuple[str | None, str | None]:
    if ref.block_id is None:
        texts = [
            part["text"]
            for part in event["content"]
            if part["kind"] == "text" and isinstance(part["text"], str) and part["text"]
        ]
        return ("\n\n".join(texts) if texts else None), None
    block = next(part for part in event["content"] if part["id"] == ref.block_id)
    text = block["text"]
    if not isinstance(text, str):
        return None, block["kind"]
    if ref.text_start is not None:
        text = text[ref.text_start : ref.text_end]
    return text, block["kind"]


def _resolve(
    document: BundleDocument, conversations: dict[tuple[str, str], _Conversation]
) -> tuple[ResolvedItem, ...]:
    paths: dict[str, list[str]] = {}
    for item in document.items:
        conversation = conversations[(item.ref.conversation_id, item.ref.revision)]
        path = conversation.ancestors(item.ref.event_id)
        if len(path) > len(paths.get(item.ref.conversation_id, [])):
            paths[item.ref.conversation_id] = path
    previous: dict[str, int] = {}
    resolved: list[ResolvedItem] = []
    for item in document.items:
        ref = item.ref
        conversation = conversations[(ref.conversation_id, ref.revision)]
        event = conversation.events[ref.event_id]
        position = paths[ref.conversation_id].index(ref.event_id)
        before = previous.get(ref.conversation_id)
        omitted = (
            position - before - 1 if before is not None and position > before else None
        )
        previous[ref.conversation_id] = position
        excerpt, block_kind = _excerpt(event, ref)
        resolved.append(
            ResolvedItem(
                item=item,
                conversation_title=conversation.title,
                conversation_is_latest=conversation.is_latest,
                event_role=event["role"],
                event_kind=event["kind"],
                occurred_at=event["occurred_at"],
                block_kind=block_kind,
                excerpt=excerpt,
                omitted_before=omitted,
            )
        )
    return tuple(resolved)


def _checked(
    session: Session, document: BundleDocument
) -> dict[tuple[str, str], _Conversation]:
    conversations = _load_conversations(session, [item.ref for item in document.items])
    issues = _validate(document, conversations)
    if issues:
        raise BundleInvalid(issues)
    return conversations


def _detail(
    session: Session, bundle: EvidenceBundle, number: int | None = None
) -> BundleDetail:
    rows = list(
        session.execute(
            select(EvidenceBundleRevision)
            .where(EvidenceBundleRevision.bundle_id == bundle.id)
            .order_by(EvidenceBundleRevision.number.desc())
        ).scalars()
    )
    selected = next(
        (row for row in rows if row.number == (number or bundle.latest_revision)),
        None,
    )
    if selected is None:
        raise BundleNotFound(bundle.id)
    document = BundleDocument.model_validate(selected.document)
    conversations = _load_conversations(session, [item.ref for item in document.items])
    return BundleDetail(
        id=bundle.id,
        revision=selected.number,
        latest_revision=bundle.latest_revision,
        origin=selected.origin,
        producer=selected.producer,
        provenance=_provenance(selected),
        request_id=bundle.request_id,
        created_at=bundle.created_at,
        updated_at=bundle.updated_at,
        document=document,
        items=_resolve(document, conversations),
        revisions=tuple(
            BundleRevisionRef(
                number=row.number,
                origin=row.origin,
                producer=row.producer,
                provenance=_provenance(row),
                created_at=row.created_at,
            )
            for row in rows
        ),
    )


def _provenance(row: EvidenceBundleRevision) -> RunProvenance | None:
    return (
        None if row.provenance is None else RunProvenance.model_validate(row.provenance)
    )


def find_bundle_by_request_id(session: Session, request_id: str) -> BundleDetail | None:
    """Return the bundle a creation request already produced, if any."""
    bundle = session.execute(
        select(EvidenceBundle).where(EvidenceBundle.request_id == request_id)
    ).scalar_one_or_none()
    return None if bundle is None else _detail(session, bundle)


def create_bundle(
    session: Session,
    document: BundleDocument,
    *,
    origin: str = "human",
    producer: str = "web",
    provenance: RunProvenance | None = None,
    request_id: str | None = None,
) -> BundleDetail:
    """Validate and store a new bundle as revision 1.

    A ``request_id`` makes creation idempotent: callers check
    :func:`find_bundle_by_request_id` first, and the unique column rejects a
    second bundle for the same request if two callers race.
    """
    _checked(session, document)
    now = utc_now()
    bundle = EvidenceBundle(
        id=f"bundle-{uuid.uuid4().hex}",
        latest_revision=1,
        request_id=request_id,
        created_at=now,
        updated_at=now,
    )
    session.add(bundle)
    session.add(
        EvidenceBundleRevision(
            bundle_id=bundle.id,
            number=1,
            document=document.model_dump(mode="json"),
            origin=origin,
            producer=producer,
            provenance=None
            if provenance is None
            else provenance.model_dump(mode="json"),
            created_at=now,
        )
    )
    session.commit()
    return _detail(session, bundle)


def update_bundle(
    session: Session,
    bundle_id: str,
    document: BundleDocument,
    *,
    base_revision: int,
    origin: str = "human",
    producer: str = "web",
    provenance: RunProvenance | None = None,
) -> BundleDetail:
    """Store a new revision unless the bundle changed or the content is unchanged."""
    bundle = session.get(EvidenceBundle, bundle_id)
    if bundle is None:
        raise BundleNotFound(bundle_id)
    if base_revision != bundle.latest_revision:
        raise BundleConflict(bundle.latest_revision)
    current = session.get(EvidenceBundleRevision, (bundle_id, bundle.latest_revision))
    serialized = document.model_dump(mode="json")
    if current is not None and current.document == serialized:
        return _detail(session, bundle)
    _checked(session, document)
    now = utc_now()
    bundle.latest_revision += 1
    bundle.updated_at = now
    session.add(
        EvidenceBundleRevision(
            bundle_id=bundle_id,
            number=bundle.latest_revision,
            document=serialized,
            origin=origin,
            producer=producer,
            provenance=None
            if provenance is None
            else provenance.model_dump(mode="json"),
            created_at=now,
        )
    )
    session.commit()
    return _detail(session, bundle)


def get_bundle(
    session: Session, bundle_id: str, *, revision: int | None = None
) -> BundleDetail:
    """Return the latest or a requested revision of one bundle, resolved."""
    bundle = session.get(EvidenceBundle, bundle_id)
    if bundle is None:
        raise BundleNotFound(bundle_id)
    return _detail(session, bundle, revision)


def list_bundles(
    session: Session,
    *,
    conversation_id: str | None = None,
    origin: str | None = None,
    status: str | None = None,
    run_id: str | None = None,
) -> tuple[BundleSummary, ...]:
    """List latest bundle revisions, most recently updated first.

    ``origin``, ``status``, and ``run_id`` filter on the latest revision, so a
    generated draft that a human later reviewed no longer counts as generated.
    """
    query = (
        select(EvidenceBundle, EvidenceBundleRevision)
        .join(
            EvidenceBundleRevision,
            (EvidenceBundleRevision.bundle_id == EvidenceBundle.id)
            & (EvidenceBundleRevision.number == EvidenceBundle.latest_revision),
        )
        .order_by(EvidenceBundle.updated_at.desc(), EvidenceBundle.id)
    )
    if origin is not None:
        query = query.where(EvidenceBundleRevision.origin == origin)
    rows = session.execute(query).all()
    summaries: list[BundleSummary] = []
    for bundle, revision in rows:
        document = BundleDocument.model_validate(revision.document)
        if status is not None and document.status != status:
            continue
        revision_run = (
            None if revision.provenance is None else revision.provenance.get("run_id")
        )
        if run_id is not None and revision_run != run_id:
            continue
        cited = tuple(
            dict.fromkeys(item.ref.conversation_id for item in document.items)
        )
        if conversation_id is not None and conversation_id not in cited:
            continue
        summaries.append(
            BundleSummary(
                id=bundle.id,
                revision=revision.number,
                summary=document.summary,
                objective=document.objective,
                goal=document.goal,
                status=document.status,
                origin=revision.origin,
                producer=revision.producer,
                run_id=revision_run,
                item_count=len(document.items),
                conversation_ids=cited,
                updated_at=bundle.updated_at,
            )
        )
    return tuple(summaries)
