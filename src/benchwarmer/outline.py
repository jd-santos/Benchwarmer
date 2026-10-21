"""Deterministic conversation outlines, version 1.

An outline describes what a captured conversation revision contains without
reading it as prose: each event's role, sizes, tool activity, Markdown headings
found in captured text, and context boundaries, plus the root-to-leaf paths and
the exchanges and segments along each path. It reports only what the normalized
conversation records. It never infers timing, tool names, or hidden steps, and
it does not run model work.

Text offsets count Unicode code points and are half-open, matching
``benchwarmer.evidence.EvidenceRef``: a heading's range cites its line.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
import re
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

OUTLINE_SCHEMA_VERSION = 1
OUTLINE_PRODUCER = "benchwarmer.outline"
OUTLINE_PRODUCER_VERSION = "1"
PREVIEW_CHARS = 160

EventKind = Literal["message", "compaction", "configuration", "unknown"]
EventRole = Literal["system", "developer", "user", "assistant", "tool", "unknown"]
BlockKind = Literal[
    "text", "reasoning", "tool_call", "tool_result", "attachment", "unknown"
]
Boundary = Literal["compaction", "configuration"]

_HEADING = re.compile(r"^(#{1,6}) +(.*)$")
_HEADING_TAIL = re.compile(r"\s+#+\s*$")
_TOOL_NAME = re.compile(r"^[A-Za-z0-9_.:/-]{1,80}$")


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class Heading(_Strict):
    """A Markdown ATX heading line found in one captured text block."""

    id: str
    block_id: str
    level: Annotated[int, Field(ge=1, le=6)]
    label: str
    text_start: Annotated[int, Field(ge=0)]
    text_end: Annotated[int, Field(ge=0)]


class ToolActivity(_Strict):
    """One tool call or result block; the name is reported only when captured."""

    block_id: str
    kind: Literal["tool_call", "tool_result"]
    tool_call_id: str
    tool_name: str | None
    chars: int | None


class OutlineEvent(_Strict):
    """What one event contains, measured rather than read."""

    id: str
    native_id: str
    ordinal: int
    parent_id: str | None
    kind: EventKind
    role: EventRole
    occurred_at: str | None
    boundary: Boundary | None
    text_chars: int
    reasoning_chars: int
    text_captured: bool
    block_counts: dict[BlockKind, int]
    tools: list[ToolActivity]
    headings: list[Heading]
    preview: str | None


class Exchange(_Strict):
    """A user turn and the events that follow it on one path."""

    id: str
    user_event_id: str | None
    event_ids: list[str]
    assistant_event_count: int
    tool_call_count: int
    assistant_text_chars: int
    heading_count: int


class Segment(_Strict):
    """A contiguous stretch of one path between context boundaries."""

    id: str
    event_ids: list[str]
    opened_by: Literal["start", "compaction", "configuration"]
    closed_by: Literal["end", "compaction", "configuration"]


class PathOutline(_Strict):
    """One root-to-leaf execution path with its exchanges and segments."""

    id: str
    leaf_event_id: str
    is_original: bool
    fork_event_id: str | None
    divergent_event_id: str | None
    event_ids: list[str]
    exchanges: list[Exchange]
    segments: list[Segment]


class ConversationOutline(_Strict):
    """The deterministic outline of one conversation revision."""

    schema_version: Literal[1] = OUTLINE_SCHEMA_VERSION
    producer: str = OUTLINE_PRODUCER
    producer_version: str = OUTLINE_PRODUCER_VERSION
    conversation_id: str
    revision: str
    event_count: int
    coverage: dict[str, str]
    events: list[OutlineEvent]
    paths: list[PathOutline]
    notes: list[str]


class PathSpec(_Strict):
    """The branch facts an outline needs, as the library derives them."""

    id: str
    leaf_event_id: str
    event_ids: list[str]
    fork_event_id: str | None
    divergent_event_id: str | None
    is_original: bool


_NOTES = [
    "Sizes count Unicode code points of captured text; uncaptured text counts 0.",
    "tool_name repeats a tool_call block's captured text only when it is a bare "
    "identifier; nothing is inferred from arguments or results.",
    "Boundaries are captured compaction and configuration events. Segments hold "
    "the events between them; exchanges start at each user message and ignore "
    "boundaries.",
    "Timing, latency, and hidden steps are not derived.",
]


def find_headings(text: str, block_id: str) -> list[Heading]:
    """Find ATX headings line by line, with code-point ranges into ``text``."""
    headings: list[Heading] = []
    offset = 0
    for line in text.splitlines(keepends=True):
        body = line.rstrip("\r\n")
        match = _HEADING.match(body)
        if match is not None:
            label = _HEADING_TAIL.sub("", match.group(2)).strip()
            if label:
                headings.append(
                    Heading(
                        id=f"{block_id}::h{len(headings)}",
                        block_id=block_id,
                        level=len(match.group(1)),
                        label=label,
                        text_start=offset,
                        text_end=offset + len(body),
                    )
                )
        offset += len(line)
    return headings


def _preview(texts: Iterable[str]) -> str | None:
    for text in texts:
        collapsed = " ".join(text.split())
        if collapsed:
            return collapsed[:PREVIEW_CHARS]
    return None


def outline_event(event: dict[str, Any]) -> OutlineEvent:
    """Measure one normalized event."""
    counts: dict[BlockKind, int] = {}
    tools: list[ToolActivity] = []
    headings: list[Heading] = []
    texts: list[str] = []
    text_chars = reasoning_chars = 0
    text_captured = False
    for block in event["content"]:
        kind: BlockKind = block["kind"]
        counts[kind] = counts.get(kind, 0) + 1
        text = block["text"] if isinstance(block["text"], str) else None
        if kind == "text":
            if text is not None:
                text_captured = True
                text_chars += len(text)
                texts.append(text)
                headings.extend(find_headings(text, block["id"]))
        elif kind == "reasoning":
            reasoning_chars += len(text) if text is not None else 0
        elif kind in {"tool_call", "tool_result"}:
            name = None
            if kind == "tool_call" and text is not None and _TOOL_NAME.match(text):
                name = text
            tools.append(
                ToolActivity(
                    block_id=block["id"],
                    kind=kind,
                    tool_call_id=block["tool_call_id"],
                    tool_name=name,
                    chars=len(text) if text is not None else None,
                )
            )
    kind_value: EventKind = event["kind"]
    boundary: Boundary | None = (
        kind_value if kind_value in {"compaction", "configuration"} else None  # type: ignore[assignment]
    )
    return OutlineEvent(
        id=event["id"],
        native_id=event["native_id"],
        ordinal=event["ordinal"],
        parent_id=event["parent_id"],
        kind=kind_value,
        role=event["role"],
        occurred_at=event["occurred_at"],
        boundary=boundary,
        text_chars=text_chars,
        reasoning_chars=reasoning_chars,
        text_captured=text_captured,
        block_counts=counts,
        tools=tools,
        headings=headings,
        preview=_preview(texts),
    )


def _exchanges(path_id: str, events: Sequence[OutlineEvent]) -> list[Exchange]:
    groups: list[tuple[str | None, list[OutlineEvent]]] = []
    for event in events:
        if event.kind == "message" and event.role == "user":
            groups.append((event.id, [event]))
        elif groups:
            groups[-1][1].append(event)
        else:
            groups.append((None, [event]))
    exchanges: list[Exchange] = []
    for index, (user_event_id, members) in enumerate(groups):
        assistant = [
            m for m in members if m.kind == "message" and m.role == "assistant"
        ]
        exchanges.append(
            Exchange(
                id=f"{path_id}:x{index}",
                user_event_id=user_event_id,
                event_ids=[m.id for m in members],
                assistant_event_count=len(assistant),
                tool_call_count=sum(
                    1 for m in members for t in m.tools if t.kind == "tool_call"
                ),
                assistant_text_chars=sum(m.text_chars for m in assistant),
                heading_count=sum(len(m.headings) for m in assistant),
            )
        )
    return exchanges


def _segments(path_id: str, events: Sequence[OutlineEvent]) -> list[Segment]:
    segments: list[Segment] = []
    opened_by: Literal["start", "compaction", "configuration"] = "start"
    current: list[str] = []
    for event in events:
        if event.boundary is None:
            current.append(event.id)
            continue
        segments.append(
            Segment(
                id=f"{path_id}:s{len(segments)}",
                event_ids=current,
                opened_by=opened_by,
                closed_by=event.boundary,
            )
        )
        opened_by = event.boundary
        current = []
    segments.append(
        Segment(
            id=f"{path_id}:s{len(segments)}",
            event_ids=current,
            opened_by=opened_by,
            closed_by="end",
        )
    )
    return segments


def build_outline(
    *,
    conversation_id: str,
    revision: str,
    events: Sequence[dict[str, Any]],
    paths: Sequence[PathSpec],
    coverage: dict[str, str],
) -> ConversationOutline:
    """Outline one validated conversation revision and its derived paths."""
    measured = [outline_event(event) for event in events]
    by_id = {event.id: event for event in measured}
    outlined_paths: list[PathOutline] = []
    for path in paths:
        along = [by_id[event_id] for event_id in path.event_ids]
        outlined_paths.append(
            PathOutline(
                id=path.id,
                leaf_event_id=path.leaf_event_id,
                is_original=path.is_original,
                fork_event_id=path.fork_event_id,
                divergent_event_id=path.divergent_event_id,
                event_ids=list(path.event_ids),
                exchanges=_exchanges(path.id, along),
                segments=_segments(path.id, along),
            )
        )
    return ConversationOutline(
        conversation_id=conversation_id,
        revision=revision,
        event_count=len(measured),
        coverage=dict(coverage),
        events=measured,
        paths=outlined_paths,
        notes=list(_NOTES),
    )
