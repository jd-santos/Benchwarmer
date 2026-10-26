"""Draft, split, check, and version tasks prepared from reviewed bundles.

A task version pins one bundle revision. The cut point divides that bundle's
conversation into what the candidate sees and what only the judge sees; the
split is computed here from the stored conversation, never trusted from the
document. Leakage flags are deterministic text checks a reviewer must accept
one by one before approval. Nothing here starts model work.
"""

from __future__ import annotations

from dataclasses import dataclass
import datetime as dt
import re
from typing import Any
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from benchwarmer.evidence import BundleDocument, EvidenceRef
from benchwarmer.models.evidence_bundle import EvidenceBundle, EvidenceBundleRevision
from benchwarmer.models.source import utc_now
from benchwarmer.models.task_version import Task, TaskVersion
from benchwarmer.services.evidence_bundles import LoadedConversation, load_conversations
from benchwarmer.tasks import (
    Criterion,
    CutPoint,
    Reconstruction,
    TaskDocument,
    TaskKind,
)

# Roles whose evidence is the historical answer or what followed it. Seeing
# one of these before the cut point means the candidate is handed the answer.
_ANSWER_ROLES = frozenset({"action", "result", "correction"})
# Word runs this long shared between a criterion and the historical answer
# read as a quote of the answer rather than a description of behavior.
_CRITERION_RUN = 8
# Word runs this long from a judge-side assistant turn found in the candidate
# section mean the answer was already in the transcript before the cut.
_CANDIDATE_RUN = 12
_PREVIEW = 160
_WORD = re.compile(r"[\w']+")


class TaskNotFound(LookupError):
    """Raised when a task or a requested task version does not exist."""


class TaskConflict(RuntimeError):
    """Raised when a save is based on a version that is no longer the latest."""

    def __init__(self, latest_version: int) -> None:
        super().__init__("task changed since it was loaded")
        self.latest_version = latest_version


@dataclass(frozen=True)
class TaskIssue:
    """Why a task document cannot be saved as given."""

    code: str
    message: str
    criterion_id: str | None = None


class TaskInvalid(ValueError):
    """Raised when a task document is incoherent with its bundle or conversation."""

    def __init__(self, issues: tuple[TaskIssue, ...]) -> None:
        super().__init__("task is invalid")
        self.issues = issues


@dataclass(frozen=True)
class LeakageFlag:
    """One automatic sign that the candidate section may reveal the answer.

    ``id`` is stable for the same document and conversation, so a leakage
    review can list the flags it accepted by id.
    """

    id: str
    code: str
    message: str
    event_id: str | None = None
    criterion_id: str | None = None
    item_index: int | None = None


@dataclass(frozen=True)
class SplitEvent:
    """One event on the task's conversation path, placed on one side of the cut."""

    event_id: str
    role: str
    kind: str
    occurred_at: str | None
    preview: str | None
    # Bundle item roles citing this event, in item order.
    cited_as: tuple[str, ...]


@dataclass(frozen=True)
class TaskSplit:
    """What the candidate sees and what only the judge sees."""

    conversation_id: str
    revision: str
    conversation_title: str | None
    candidate: tuple[SplitEvent, ...]
    judge: tuple[SplitEvent, ...]
    # Events the bundle cites in other conversations; always judge-only.
    other_judge: tuple[SplitEvent, ...]


@dataclass(frozen=True)
class TaskVersionRef:
    number: int
    status: str
    producer: str
    created_at: dt.datetime


@dataclass(frozen=True)
class TaskDetail:
    id: str
    version: int
    latest_version: int
    producer: str
    created_at: dt.datetime
    updated_at: dt.datetime
    document: TaskDocument
    bundle: BundleDocument
    bundle_latest_revision: int
    split: TaskSplit
    flags: tuple[LeakageFlag, ...]
    versions: tuple[TaskVersionRef, ...]


@dataclass(frozen=True)
class TaskSummary:
    id: str
    version: int
    status: str
    kind: str
    summary: str
    objective: str
    objective_type: str
    family: str
    partition: str | None
    bundle_id: str
    bundle_revision: int
    criterion_count: int
    updated_at: dt.datetime


@dataclass(frozen=True)
class TaskDraft:
    """A starting document and its split, not yet saved."""

    document: TaskDocument
    bundle: BundleDocument
    split: TaskSplit
    flags: tuple[LeakageFlag, ...]


@dataclass(frozen=True)
class _Resolved:
    bundle: BundleDocument
    conversations: dict[tuple[str, str], LoadedConversation]
    conversation: LoadedConversation
    path: list[str]
    cut_index: int


def _words(text: str) -> list[str]:
    return [word.casefold() for word in _WORD.findall(text)]


def _runs(words: list[str], length: int) -> set[tuple[str, ...]]:
    if len(words) < length:
        return set()
    return {tuple(words[i : i + length]) for i in range(len(words) - length + 1)}


def _texts(event: dict[str, Any], kinds: frozenset[str]) -> list[str]:
    return [
        part["text"]
        for part in event["content"]
        if part["kind"] in kinds and isinstance(part["text"], str) and part["text"]
    ]


def _preview(event: dict[str, Any]) -> str | None:
    texts = _texts(event, frozenset({"text"})) or _texts(
        event, frozenset({"tool_result", "tool_call"})
    )
    if not texts:
        return None
    flat = " ".join(texts[0].split())
    return flat if len(flat) <= _PREVIEW else flat[: _PREVIEW - 1] + "…"


def _load_bundle(
    session: Session, bundle_id: str, bundle_revision: int
) -> tuple[EvidenceBundle, BundleDocument]:
    bundle = session.get(EvidenceBundle, bundle_id)
    if bundle is None:
        raise TaskInvalid(
            (TaskIssue("bundle_not_found", "The task's bundle is not in the library."),)
        )
    row = session.get(EvidenceBundleRevision, (bundle_id, bundle_revision))
    if row is None:
        raise TaskInvalid(
            (
                TaskIssue(
                    "bundle_revision_not_found", "That bundle revision does not exist."
                ),
            )
        )
    return bundle, BundleDocument.model_validate(row.document)


def _resolve(
    session: Session, document: TaskDocument, bundle: BundleDocument
) -> _Resolved:
    refs = [item.ref for item in bundle.items]
    cut = document.cut_point
    conversations = load_conversations(
        session, [*refs, EvidenceRef(**cut.model_dump())]
    )
    conversation = conversations.get((cut.conversation_id, cut.revision))
    if conversation is None:
        raise TaskInvalid(
            (
                TaskIssue(
                    "cut_point_conversation_not_found",
                    "The cut point names a conversation revision not in the library.",
                ),
            )
        )
    cited = [
        ref.event_id
        for ref in refs
        if ref.conversation_id == cut.conversation_id and ref.revision == cut.revision
    ]
    if not cited:
        raise TaskInvalid(
            (
                TaskIssue(
                    "cut_point_not_cited",
                    "The cut point must lie in a conversation the bundle cites.",
                ),
            )
        )
    if cut.event_id not in conversation.events:
        raise TaskInvalid(
            (
                TaskIssue(
                    "cut_point_event_not_found",
                    "The cut point event is not in that revision.",
                ),
            )
        )
    # The bundle's items lie on one path; take the deepest cited event's path,
    # extended to the cut point when the cut lies below it.
    deepest = max((conversation.ancestors(event_id) for event_id in cited), key=len)
    cut_path = conversation.ancestors(cut.event_id)
    if cut.event_id in deepest:
        path = deepest
    elif cut_path[: len(deepest)] == deepest:
        path = cut_path
    else:
        raise TaskInvalid(
            (
                TaskIssue(
                    "cut_point_off_path",
                    "The cut point is on a different branch from the bundle's evidence.",
                ),
            )
        )
    return _Resolved(
        bundle=bundle,
        conversations=conversations,
        conversation=conversation,
        path=path,
        cut_index=path.index(cut.event_id),
    )


def _cited_roles(bundle: BundleDocument) -> dict[tuple[str, str], list[str]]:
    roles: dict[tuple[str, str], list[str]] = {}
    for item in bundle.items:
        roles.setdefault((item.ref.conversation_id, item.ref.event_id), []).append(
            item.role
        )
    return roles


def _split_event(
    conversation: LoadedConversation,
    event_id: str,
    roles: dict[tuple[str, str], list[str]],
) -> SplitEvent:
    event = conversation.events[event_id]
    return SplitEvent(
        event_id=event_id,
        role=event["role"],
        kind=event["kind"],
        occurred_at=event["occurred_at"],
        preview=_preview(event),
        cited_as=tuple(roles.get((conversation.document["id"], event_id), ())),
    )


def _split(resolved: _Resolved) -> TaskSplit:
    roles = _cited_roles(resolved.bundle)
    conversation = resolved.conversation
    before = resolved.path[: resolved.cut_index + 1]
    after = resolved.path[resolved.cut_index + 1 :]
    other: list[SplitEvent] = []
    seen: set[tuple[str, str]] = set()
    for item in resolved.bundle.items:
        key = (item.ref.conversation_id, item.ref.event_id)
        if item.ref.conversation_id == conversation.document["id"] or key in seen:
            continue
        seen.add(key)
        cited = resolved.conversations[(item.ref.conversation_id, item.ref.revision)]
        other.append(_split_event(cited, item.ref.event_id, roles))
    return TaskSplit(
        conversation_id=conversation.document["id"],
        revision=conversation.row.revision,
        conversation_title=conversation.title,
        candidate=tuple(_split_event(conversation, e, roles) for e in before),
        judge=tuple(_split_event(conversation, e, roles) for e in after),
        other_judge=tuple(other),
    )


def _flags(document: TaskDocument, resolved: _Resolved) -> tuple[LeakageFlag, ...]:
    flags: list[LeakageFlag] = []
    conversation = resolved.conversation
    cut_event = conversation.events[document.cut_point.event_id]
    before = resolved.path[: resolved.cut_index + 1]
    after = resolved.path[resolved.cut_index + 1 :]

    if cut_event["role"] == "assistant":
        flags.append(
            LeakageFlag(
                id="cut_after_assistant",
                code="cut_after_assistant",
                message="The cut point is an assistant turn, so the candidate would "
                "continue the historical answer rather than produce its own.",
                event_id=cut_event["id"],
            )
        )
    if not after:
        flags.append(
            LeakageFlag(
                id="no_historical_answer",
                code="no_historical_answer",
                message="Nothing follows the cut point in this conversation, so the "
                "judge has no historical answer to compare against.",
            )
        )

    before_set = set(before)
    for index, item in enumerate(resolved.bundle.items):
        if (
            item.role in _ANSWER_ROLES
            and item.ref.conversation_id == conversation.document["id"]
            and item.ref.event_id in before_set
        ):
            flags.append(
                LeakageFlag(
                    id=f"answer_before_cut:{index}",
                    code="answer_before_cut",
                    message=f"Item {index + 1} is cited as a {item.role} but lies "
                    "before the cut point, so the candidate sees it.",
                    event_id=item.ref.event_id,
                    item_index=index,
                )
            )

    judge_answer_runs: set[tuple[str, ...]] = set()
    judge_runs_by_event: dict[str, set[tuple[str, ...]]] = {}
    for event_id in after:
        event = conversation.events[event_id]
        if event["role"] != "assistant":
            continue
        words = _words(" ".join(_texts(event, frozenset({"text"}))))
        judge_answer_runs |= _runs(words, _CRITERION_RUN)
        judge_runs_by_event[event_id] = _runs(words, _CANDIDATE_RUN)

    if judge_answer_runs:
        for criterion in document.criteria:
            if _runs(_words(criterion.statement), _CRITERION_RUN) & judge_answer_runs:
                flags.append(
                    LeakageFlag(
                        id=f"criterion_quotes_answer:{criterion.id}",
                        code="criterion_quotes_answer",
                        message=f"Criterion '{criterion.id}' repeats a run of "
                        f"{_CRITERION_RUN} or more words from the historical "
                        "answer. Describe the behavior instead of quoting it.",
                        criterion_id=criterion.id,
                    )
                )

    candidate_runs: set[tuple[str, ...]] = set()
    for event_id in before:
        event = conversation.events[event_id]
        words = _words(" ".join(_texts(event, frozenset({"text", "tool_result"}))))
        candidate_runs |= _runs(words, _CANDIDATE_RUN)
    for event_id, runs in judge_runs_by_event.items():
        if runs & candidate_runs:
            flags.append(
                LeakageFlag(
                    id=f"judge_text_in_candidate:{event_id}",
                    code="judge_text_in_candidate",
                    message="A run of words from a historical assistant turn after "
                    "the cut point already appears in the candidate section.",
                    event_id=event_id,
                )
            )
    return tuple(flags)


def _approval_issues(
    document: TaskDocument, bundle: BundleDocument, flags: tuple[LeakageFlag, ...]
) -> tuple[TaskIssue, ...]:
    if document.status != "approved":
        return ()
    issues: list[TaskIssue] = []
    if bundle.status != "reviewed":
        issues.append(
            TaskIssue(
                "bundle_not_reviewed",
                "Only a task prepared from a reviewed bundle revision can be approved.",
            )
        )
    accepted = set(
        document.leakage_review.accepted_flags if document.leakage_review else ()
    )
    for flag in flags:
        if flag.id not in accepted:
            issues.append(
                TaskIssue(
                    "unaccepted_leakage_flag",
                    f"Leakage flag '{flag.id}' has not been accepted by the reviewer.",
                    criterion_id=flag.criterion_id,
                )
            )
    return tuple(issues)


def _checked(
    session: Session, document: TaskDocument
) -> tuple[BundleDocument, int, TaskSplit, tuple[LeakageFlag, ...]]:
    bundle_row, bundle = _load_bundle(
        session, document.bundle_id, document.bundle_revision
    )
    resolved = _resolve(session, document, bundle)
    flags = _flags(document, resolved)
    issues = _approval_issues(document, bundle, flags)
    if issues:
        raise TaskInvalid(issues)
    return bundle, bundle_row.latest_revision, _split(resolved), flags


def _default_cut(
    bundle: BundleDocument, resolved_path: list[str], conversation: LoadedConversation
) -> str:
    """The last user turn before the first cited answer, or the first cited event."""
    first_answer = None
    for item in bundle.items:
        if (
            item.role in _ANSWER_ROLES
            and item.ref.conversation_id == conversation.document["id"]
            and item.ref.event_id in resolved_path
        ):
            position = resolved_path.index(item.ref.event_id)
            if first_answer is None or position < first_answer:
                first_answer = position
    limit = first_answer if first_answer is not None else len(resolved_path)
    for event_id in reversed(resolved_path[:limit]):
        if conversation.events[event_id]["role"] == "user":
            return event_id
    return resolved_path[0]


def _default_kind(conversation: LoadedConversation, path: list[str]) -> TaskKind:
    for event_id in path:
        for part in conversation.events[event_id]["content"]:
            if part["kind"] == "tool_call":
                return "agent"
    return "chat"


def draft_task(
    session: Session, bundle_id: str, *, bundle_revision: int | None = None
) -> TaskDraft:
    """Propose a starting task document for a bundle without saving it."""
    bundle_row = session.get(EvidenceBundle, bundle_id)
    if bundle_row is None:
        raise TaskInvalid(
            (TaskIssue("bundle_not_found", "The task's bundle is not in the library."),)
        )
    number = bundle_revision or bundle_row.latest_revision
    _, bundle = _load_bundle(session, bundle_id, number)
    first = bundle.items[0].ref
    conversations = load_conversations(session, [item.ref for item in bundle.items])
    conversation = conversations[(first.conversation_id, first.revision)]
    cited = [
        item.ref.event_id
        for item in bundle.items
        if item.ref.conversation_id == first.conversation_id
    ]
    path = max((conversation.ancestors(event_id) for event_id in cited), key=len)
    document = TaskDocument(
        bundle_id=bundle_id,
        bundle_revision=number,
        kind=_default_kind(conversation, path),
        summary=bundle.summary,
        objective=bundle.objective,
        objective_type=bundle.objective_type,
        family=conversation.document["id"],
        cut_point=CutPoint(
            conversation_id=first.conversation_id,
            revision=first.revision,
            event_id=_default_cut(bundle, path, conversation),
        ),
        reconstruction=Reconstruction(
            level="prompt_only",
            gaps=list(bundle.missing_evidence),
        ),
        criteria=[],
    )
    resolved = _resolve(session, document, bundle)
    return TaskDraft(
        document=document,
        bundle=bundle,
        split=_split(resolved),
        flags=_flags(document, resolved),
    )


def _detail(session: Session, task: Task, number: int | None = None) -> TaskDetail:
    rows = list(
        session.execute(
            select(TaskVersion)
            .where(TaskVersion.task_id == task.id)
            .order_by(TaskVersion.number.desc())
        ).scalars()
    )
    selected = next(
        (row for row in rows if row.number == (number or task.latest_version)), None
    )
    if selected is None:
        raise TaskNotFound(task.id)
    document = TaskDocument.model_validate(selected.document)
    bundle_row, bundle = _load_bundle(
        session, document.bundle_id, document.bundle_revision
    )
    resolved = _resolve(session, document, bundle)
    return TaskDetail(
        id=task.id,
        version=selected.number,
        latest_version=task.latest_version,
        producer=selected.producer,
        created_at=task.created_at,
        updated_at=task.updated_at,
        document=document,
        bundle=bundle,
        bundle_latest_revision=bundle_row.latest_revision,
        split=_split(resolved),
        flags=_flags(document, resolved),
        versions=tuple(
            TaskVersionRef(
                number=row.number,
                status=row.status,
                producer=row.producer,
                created_at=row.created_at,
            )
            for row in rows
        ),
    )


def create_task(
    session: Session, document: TaskDocument, *, producer: str = "web"
) -> TaskDetail:
    """Validate and store a new task as version 1."""
    _checked(session, document)
    now = utc_now()
    task = Task(
        id=f"task-{uuid.uuid4().hex}",
        bundle_id=document.bundle_id,
        latest_version=1,
        created_at=now,
        updated_at=now,
    )
    session.add(task)
    session.add(
        TaskVersion(
            task_id=task.id,
            number=1,
            document=document.model_dump(mode="json"),
            status=document.status,
            family=document.family,
            producer=producer,
            created_at=now,
        )
    )
    session.commit()
    return _detail(session, task)


def _content(serialized: dict[str, Any]) -> dict[str, Any]:
    """A document without the fields that may change on an approved version."""
    return {
        key: value
        for key, value in serialized.items()
        if key not in ("status", "leakage_review", "reviewer_notes", "partition")
    }


def update_task(
    session: Session,
    task_id: str,
    document: TaskDocument,
    *,
    base_version: int,
    producer: str = "web",
) -> TaskDetail:
    """Store a new version unless the task changed, is retired, or is unchanged.

    An approved version is immutable in content: a content change is stored
    as a new ``draft`` version, never as a changed approved one. A retired
    version is terminal.
    """
    task = session.get(Task, task_id)
    if task is None:
        raise TaskNotFound(task_id)
    if base_version != task.latest_version:
        raise TaskConflict(task.latest_version)
    current = session.get(TaskVersion, (task_id, task.latest_version))
    serialized = document.model_dump(mode="json")
    if current is not None and current.document == serialized:
        return _detail(session, task)
    if document.bundle_id != task.bundle_id:
        raise TaskInvalid(
            (TaskIssue("bundle_changed", "A task cannot move to another bundle."),)
        )
    if current is not None and current.status == "retired":
        raise TaskInvalid(
            (TaskIssue("task_retired", "A retired task cannot be changed."),)
        )
    if (
        current is not None
        and current.status == "approved"
        and document.status == "approved"
        and _content(current.document) != _content(serialized)
    ):
        raise TaskInvalid(
            (
                TaskIssue(
                    "approved_content_changed",
                    "Changing an approved task's content creates a new draft "
                    "version; set the status to draft and approve it again.",
                ),
            )
        )
    _checked(session, document)
    now = utc_now()
    task.latest_version += 1
    task.updated_at = now
    session.add(
        TaskVersion(
            task_id=task_id,
            number=task.latest_version,
            document=serialized,
            status=document.status,
            family=document.family,
            producer=producer,
            created_at=now,
        )
    )
    session.commit()
    return _detail(session, task)


def get_task(
    session: Session, task_id: str, *, version: int | None = None
) -> TaskDetail:
    """Return the latest or a requested version of one task, with its split."""
    task = session.get(Task, task_id)
    if task is None:
        raise TaskNotFound(task_id)
    return _detail(session, task, version)


def list_tasks(
    session: Session,
    *,
    status: str | None = None,
    bundle_id: str | None = None,
    family: str | None = None,
) -> tuple[TaskSummary, ...]:
    """Summarize each task's latest version, newest first."""
    query = (
        select(Task, TaskVersion)
        .join(
            TaskVersion,
            (TaskVersion.task_id == Task.id)
            & (TaskVersion.number == Task.latest_version),
        )
        .order_by(Task.updated_at.desc(), Task.id)
    )
    if status is not None:
        query = query.where(TaskVersion.status == status)
    if bundle_id is not None:
        query = query.where(Task.bundle_id == bundle_id)
    if family is not None:
        query = query.where(TaskVersion.family == family)
    summaries: list[TaskSummary] = []
    for task, version in session.execute(query):
        document = version.document
        summaries.append(
            TaskSummary(
                id=task.id,
                version=version.number,
                status=version.status,
                kind=document["kind"],
                summary=document["summary"],
                objective=document["objective"],
                objective_type=document["objective_type"],
                family=version.family,
                partition=document.get("partition"),
                bundle_id=task.bundle_id,
                bundle_revision=document["bundle_revision"],
                criterion_count=len(document["criteria"]),
                updated_at=task.updated_at,
            )
        )
    return tuple(summaries)


__all__ = [
    "Criterion",
    "LeakageFlag",
    "SplitEvent",
    "TaskConflict",
    "TaskDetail",
    "TaskDraft",
    "TaskInvalid",
    "TaskIssue",
    "TaskNotFound",
    "TaskSplit",
    "TaskSummary",
    "TaskVersionRef",
    "create_task",
    "draft_task",
    "get_task",
    "list_tasks",
    "update_task",
]
