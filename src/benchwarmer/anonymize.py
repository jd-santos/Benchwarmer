"""Deterministic scrubbing, fidelity, and leak checks for synthetic fixtures.

The scrub pass replaces private-looking spans in normalized conversation events
with stable per-conversation placeholders. It rewrites only the matched spans:
ids, ordinals, parents, kinds, roles, block order, tool linkage, extensions, and
relationships are returned unchanged. It is a read-only transform and never
runs model work; a later, separately approved model step may turn the scrubbed
events into an invented analog.

The fidelity check compares an original conversation with a candidate fixture
conversation structurally. The leak check looks for operator terms and scrubbed
original text inside a candidate. Both return typed issue lists, and neither
copies original private text into its issues.

Text offsets count Unicode code points and are half-open, matching
``benchwarmer.evidence.EvidenceRef``.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
import re
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from benchwarmer.adapters.file_conversations import FileConversation

ANONYMIZE_SCHEMA_VERSION = 1
ANONYMIZE_PRODUCER = "benchwarmer.anonymize"
ANONYMIZE_PRODUCER_VERSION = "1"
MAX_TERMS = 200

ScrubCategory = Literal[
    "term", "email", "url", "path", "ipv6", "ipv4", "secret", "hostname"
]
EventKind = Literal["message", "compaction", "configuration", "unknown"]
EventRole = Literal["system", "developer", "user", "assistant", "tool", "unknown"]
BlockKind = Literal[
    "text", "reasoning", "tool_call", "tool_result", "attachment", "unknown"
]

Term = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
]
TermList = Annotated[list[Term], Field(max_length=MAX_TERMS)]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class ScrubSpan(_Strict):
    """One replaced span, located in the original text; the text itself is omitted."""

    event_id: str | None
    block_id: str | None
    category: ScrubCategory
    text_start: Annotated[int, Field(ge=0)]
    text_end: Annotated[int, Field(ge=0)]
    placeholder: str


class ScrubReport(_Strict):
    """What was replaced, without the original values."""

    schema_version: Literal[1] = ANONYMIZE_SCHEMA_VERSION
    producer: str = ANONYMIZE_PRODUCER
    producer_version: str = ANONYMIZE_PRODUCER_VERSION
    native_id: str
    source_version: str | None
    term_count: int
    counts: dict[ScrubCategory, int]
    placeholders: dict[str, ScrubCategory]
    spans: list[ScrubSpan]
    notes: list[str]


class FixtureBlock(_Strict):
    """A content block as `tests/fixtures` conversation files write it (no id)."""

    kind: BlockKind
    text: str | None
    tool_call_id: str | None = None
    artifact_id: str | None = None
    extensions: dict[str, Any] = {}


class FixtureEvent(_Strict):
    """An event as fixture files write it; parent_id names a native_id."""

    native_id: str
    ordinal: Annotated[int, Field(ge=0)]
    parent_id: str | None
    kind: EventKind
    role: EventRole
    occurred_at: str | None
    content: list[FixtureBlock]
    extensions: dict[str, Any] = {}


class FixtureConversation(_Strict):
    """One conversation entry of a `schema_version: 1` fixture file."""

    native_id: str
    title: str | None = None
    coverage: dict[str, str] | None = None
    usage: list[dict[str, Any]] = []
    events: list[FixtureEvent]
    relationships: list[dict[str, Any]] = []


class ScrubResult(_Strict):
    """Scrubbed events plus the fixture-shaped conversation they form."""

    title: str | None
    events: list[dict[str, Any]]
    fixture: FixtureConversation
    report: ScrubReport


class FidelityIssue(_Strict):
    """A structural difference between the original and a candidate."""

    code: Literal[
        "event_count",
        "duplicate_native_id",
        "unknown_parent",
        "ordinal",
        "parent",
        "kind",
        "role",
        "block_kinds",
        "text_captured",
        "tool_pairing",
        "extension_keys",
        "relationship_kinds",
        "title_presence",
    ]
    ordinal: int | None
    message: str


class LeakIssue(_Strict):
    """Private text found in a candidate; the text itself is not repeated."""

    code: Literal["term", "original_span"]
    location: str
    text_start: Annotated[int, Field(ge=0)]
    text_end: Annotated[int, Field(ge=0)]
    category: ScrubCategory | None


class FixtureCheck(_Strict):
    """Fidelity and leak findings for one candidate against one revision."""

    schema_version: Literal[1] = ANONYMIZE_SCHEMA_VERSION
    producer: str = ANONYMIZE_PRODUCER
    producer_version: str = ANONYMIZE_PRODUCER_VERSION
    native_id: str
    fidelity: list[FidelityIssue]
    leaks: list[LeakIssue]
    ok: bool


_NOTES = [
    "Placeholders are stable within one conversation: the same original value "
    "maps to the same placeholder in the title and every block.",
    "Only block text and the title are rewritten. Extensions, relationships, "
    "usage, and timestamps pass through unchanged; the leak check still scans "
    "them.",
    "Windows drive paths and hostnames outside the known suffix list are not "
    "detected; name them as terms.",
    "Spans are located in the original text by code-point offsets and never "
    "carry the original value.",
]

_PRIORITY: dict[ScrubCategory, int] = {
    "term": 0,
    "email": 1,
    "url": 2,
    "path": 3,
    "ipv6": 4,
    "ipv4": 5,
    "secret": 6,
    "hostname": 7,
}

_HOST_SUFFIXES = (
    "com|net|org|io|dev|ai|app|cloud|co|us|uk|ca|de|fr|eu|me|sh|xyz|tech|edu|gov|"
    "mil|int|info|biz|tv|local|lan|internal|localhost|test|example|home|corp"
)
_EMAIL = re.compile(r"(?<![\w.+-])[\w.+-]+@(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}(?!\w)")
_URL = re.compile(r"(?<![\w/])[A-Za-z][A-Za-z0-9+.-]{1,15}://[^\s<>\"'`)\]}]+")
_PATH = re.compile(
    r"(?<![\w./:])(?:~|/[A-Za-z0-9_.@+-]+)(?:/[A-Za-z0-9_.@+-]+)+/?(?![\w/])"
)
_IPV6 = re.compile(
    r"(?<![\w:.])(?:"
    r"(?:[0-9A-Fa-f]{1,4}:){7}[0-9A-Fa-f]{1,4}"
    r"|(?:[0-9A-Fa-f]{1,4}:){1,7}:"
    r"|(?:[0-9A-Fa-f]{1,4}:){1,6}:[0-9A-Fa-f]{1,4}"
    r"|(?:[0-9A-Fa-f]{1,4}:){1,5}(?::[0-9A-Fa-f]{1,4}){1,2}"
    r"|(?:[0-9A-Fa-f]{1,4}:){1,4}(?::[0-9A-Fa-f]{1,4}){1,3}"
    r"|(?:[0-9A-Fa-f]{1,4}:){1,3}(?::[0-9A-Fa-f]{1,4}){1,4}"
    r"|(?:[0-9A-Fa-f]{1,4}:){1,2}(?::[0-9A-Fa-f]{1,4}){1,5}"
    r"|[0-9A-Fa-f]{1,4}:(?::[0-9A-Fa-f]{1,4}){1,6}"
    r"|::(?:[0-9A-Fa-f]{1,4}:){0,6}[0-9A-Fa-f]{1,4}"
    r"|::"
    r")(?![\w:.])"
)
_IPV4 = re.compile(
    r"(?<![\w.])(?:(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\.){3}"
    r"(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(?!\w)(?!\.\d)"
)
_SECRET_PREFIXED = re.compile(
    r"(?<![\w-])(?:"
    r"sk-[A-Za-z0-9_-]{8,}"
    r"|sk_(?:live|test)_[A-Za-z0-9]{8,}"
    r"|gh[pousr]_[A-Za-z0-9]{20,}"
    r"|github_pat_[A-Za-z0-9_]{20,}"
    r"|AKIA[0-9A-Z]{16}"
    r"|xox[abprs]-[A-Za-z0-9-]{10,}"
    r"|AIza[0-9A-Za-z_-]{30,}"
    r"|eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"
    r")(?![\w-])"
)
_SECRET_HEX = re.compile(r"(?<![\w-])[0-9A-Fa-f]{32,}(?![\w-])")
_SECRET_BASE64 = re.compile(
    r"(?<![A-Za-z0-9+/=_-])[A-Za-z0-9+/_-]{40,}={0,2}(?![A-Za-z0-9+/=])"
)
_HOSTNAME = re.compile(
    r"(?<![\w.@/-])(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,62})\.)+"
    r"(?:" + _HOST_SUFFIXES + r")(?![\w-])(?!\.\w)"
    r"|(?<![\w.@/-])localhost(?![\w-])(?!\.\w)"
)
_EXTENSION = re.compile(r"\.([A-Za-z0-9]{1,10})$")


def _looks_random(value: str) -> bool:
    """Base64-ish runs count as secrets only when they mix character classes."""
    return (
        any(c.islower() for c in value)
        and any(c.isupper() for c in value)
        and any(c.isdigit() for c in value)
    )


def _term_pattern(terms: Sequence[str]) -> re.Pattern[str] | None:
    cleaned = sorted({t.strip() for t in terms if t.strip()}, key=len, reverse=True)
    if not cleaned:
        return None
    alternatives = "|".join(re.escape(term) for term in cleaned)
    return re.compile(rf"(?<!\w)(?:{alternatives})(?!\w)", re.IGNORECASE)


class Scrubber:
    """Stateful per-conversation scrubber with stable placeholders."""

    def __init__(self, terms: Sequence[str] = ()) -> None:
        self._terms = _term_pattern(terms)
        self._term_count = len({t.strip().casefold() for t in terms if t.strip()})
        self._placeholders: dict[tuple[ScrubCategory, str], str] = {}
        self._counters: dict[ScrubCategory, int] = {}
        self._originals: dict[str, ScrubCategory] = {}
        self.counts: dict[ScrubCategory, int] = {}
        self.spans: list[ScrubSpan] = []

    @property
    def term_count(self) -> int:
        return self._term_count

    @property
    def placeholders(self) -> dict[str, ScrubCategory]:
        """Placeholder to category, without the original values."""
        return {
            placeholder: category
            for (category, _), placeholder in self._placeholders.items()
        }

    def originals(self) -> dict[str, ScrubCategory]:
        """Replaced original texts and their categories; for the leak check only."""
        return dict(self._originals)

    def _placeholder(self, category: ScrubCategory, original: str) -> str:
        key_text = original.casefold() if category == "term" else original
        key = (category, key_text)
        existing = self._placeholders.get(key)
        if existing is not None:
            return existing
        number = self._counters.get(category, 0) + 1
        self._counters[category] = number
        if category == "path":
            match = _EXTENSION.search(original.rstrip("/"))
            suffix = f".{match.group(1)}" if match else ""
            placeholder = f"/scrubbed/path-{number}/file-{number}{suffix}"
        else:
            placeholder = f"<{category}-{number}>"
        self._placeholders[key] = placeholder
        self._originals[original] = category
        return placeholder

    def _matches(self, text: str) -> list[tuple[int, int, ScrubCategory]]:
        found: list[tuple[int, int, ScrubCategory]] = []

        def collect(
            pattern: re.Pattern[str] | None,
            category: ScrubCategory,
            accept: Callable[[str], bool] | None = None,
        ) -> None:
            if pattern is None:
                return
            for match in pattern.finditer(text):
                if accept is None or accept(match.group(0)):
                    found.append((match.start(), match.end(), category))

        collect(self._terms, "term")
        collect(_EMAIL, "email")
        collect(_URL, "url")
        collect(_PATH, "path")
        collect(_IPV6, "ipv6")
        collect(_IPV4, "ipv4")
        collect(_SECRET_PREFIXED, "secret")
        collect(_SECRET_HEX, "secret")
        collect(_SECRET_BASE64, "secret", _looks_random)
        collect(_HOSTNAME, "hostname")
        found.sort(key=lambda m: (m[0], -(m[1] - m[0]), _PRIORITY[m[2]]))
        chosen: list[tuple[int, int, ScrubCategory]] = []
        cursor = 0
        for start, end, category in found:
            if start < cursor:
                continue
            chosen.append((start, end, category))
            cursor = end
        return chosen

    def scrub_text(
        self, text: str, *, event_id: str | None, block_id: str | None
    ) -> str:
        """Replace every detected span in ``text`` and record the spans."""
        pieces: list[str] = []
        cursor = 0
        for start, end, category in self._matches(text):
            placeholder = self._placeholder(category, text[start:end])
            self.counts[category] = self.counts.get(category, 0) + 1
            self.spans.append(
                ScrubSpan(
                    event_id=event_id,
                    block_id=block_id,
                    category=category,
                    text_start=start,
                    text_end=end,
                    placeholder=placeholder,
                )
            )
            pieces.append(text[cursor:start])
            pieces.append(placeholder)
            cursor = end
        pieces.append(text[cursor:])
        return "".join(pieces)

    def scrub_event(self, event: dict[str, Any]) -> dict[str, Any]:
        """Copy one event, rewriting only captured block text."""
        content = []
        for block in event["content"]:
            text = block["text"]
            if isinstance(text, str):
                block = dict(
                    block,
                    text=self.scrub_text(
                        text, event_id=event["id"], block_id=block["id"]
                    ),
                )
            content.append(block)
        return dict(event, content=content)


def fixture_event(event: dict[str, Any]) -> FixtureEvent:
    """Drop library ids from one normalized event, keeping native linkage."""
    return FixtureEvent(
        native_id=event["native_id"],
        ordinal=event["ordinal"],
        parent_id=event["parent_id"],
        kind=event["kind"],
        role=event["role"],
        occurred_at=event["occurred_at"],
        content=[
            FixtureBlock(
                kind=block["kind"],
                text=block["text"],
                tool_call_id=block["tool_call_id"],
                artifact_id=block["artifact_id"],
                extensions=dict(block["extensions"]),
            )
            for block in event["content"]
        ],
        extensions=dict(event["extensions"]),
    )


def fixture_conversation(
    *,
    native_id: str,
    title: str | None,
    events: Sequence[dict[str, Any]],
    relationships: Sequence[dict[str, Any]],
    coverage: dict[str, str] | None,
    usage: Sequence[dict[str, Any]] = (),
) -> FixtureConversation:
    """Shape normalized events as a fixture conversation entry.

    Library events carry parent ids in library form; the fixture form names the
    parent's native id, as ``tests/fixtures`` files do.
    """
    native_by_id = {event["id"]: event["native_id"] for event in events}
    shaped = []
    for event in events:
        parent = event["parent_id"]
        shaped.append(
            fixture_event(
                dict(
                    event,
                    parent_id=native_by_id.get(parent, parent)
                    if parent is not None
                    else None,
                )
            )
        )
    return FixtureConversation(
        native_id=native_id,
        title=title,
        coverage=dict(coverage) if coverage is not None else None,
        usage=[dict(item) for item in usage],
        events=shaped,
        relationships=[dict(item) for item in relationships],
    )


_USAGE_FIELDS = ("entry_id", "record_ordinal", "provider", "model", "usage")


def fixture_usage(metadata: Sequence[tuple[str, object]]) -> list[dict[str, Any]]:
    """Keep usage observations' counts and model names; drop response ids."""
    usage: list[dict[str, Any]] = []
    for name, value in metadata:
        if name != "usage_observations" or not isinstance(value, list):
            continue
        for item in value:
            if isinstance(item, dict):
                usage.append({k: item[k] for k in _USAGE_FIELDS if k in item})
    return usage


def scrub_file_conversation(
    item: FileConversation, *, terms: Sequence[str]
) -> tuple[ScrubResult, Scrubber]:
    """Scrub one parsed source conversation without touching its native snapshot."""
    title = next(
        (str(v) for n, v in item.metadata if n == "title" and isinstance(v, str)),
        None,
    )
    return scrub_conversation(
        native_id=item.native_id,
        source_version=item.source_version,
        title=title,
        events=list(item.events),
        relationships=list(item.relationships),
        coverage=item.coverage,
        usage=fixture_usage(item.metadata),
        terms=terms,
    )


def scrub_conversation(
    *,
    native_id: str,
    source_version: str | None = None,
    title: str | None,
    events: Sequence[dict[str, Any]],
    relationships: Sequence[dict[str, Any]],
    coverage: dict[str, str] | None,
    usage: Sequence[dict[str, Any]] = (),
    terms: Sequence[str],
) -> tuple[ScrubResult, Scrubber]:
    """Scrub a conversation's title and events; the scrubber keeps the originals."""
    scrubber = Scrubber(terms)
    scrubbed_title = (
        scrubber.scrub_text(title, event_id=None, block_id=None)
        if title is not None
        else None
    )
    scrubbed_events = [scrubber.scrub_event(event) for event in events]
    report = ScrubReport(
        native_id=native_id,
        source_version=source_version,
        term_count=scrubber.term_count,
        counts=dict(scrubber.counts),
        placeholders=scrubber.placeholders,
        spans=list(scrubber.spans),
        notes=list(_NOTES),
    )
    result = ScrubResult(
        title=scrubbed_title,
        events=scrubbed_events,
        fixture=fixture_conversation(
            native_id=native_id,
            title=scrubbed_title,
            events=scrubbed_events,
            relationships=relationships,
            coverage=coverage,
            usage=usage,
        ),
        report=report,
    )
    return result, scrubber


def fidelity_issues(
    original: FixtureConversation, candidate: FixtureConversation
) -> list[FidelityIssue]:
    """Compare structure positionally, event by event in ordinal order."""
    issues: list[FidelityIssue] = []
    if (original.title is None) != (candidate.title is None):
        issues.append(
            FidelityIssue(
                code="title_presence",
                ordinal=None,
                message="the original and candidate disagree on having a title",
            )
        )
    seen: set[str] = set()
    for event in candidate.events:
        if event.native_id in seen:
            issues.append(
                FidelityIssue(
                    code="duplicate_native_id",
                    ordinal=event.ordinal,
                    message=f"candidate native_id {event.native_id!r} repeats",
                )
            )
        seen.add(event.native_id)
    for event in candidate.events:
        if event.parent_id is not None and event.parent_id not in seen:
            issues.append(
                FidelityIssue(
                    code="unknown_parent",
                    ordinal=event.ordinal,
                    message=f"candidate parent {event.parent_id!r} names no event",
                )
            )
    left = sorted(original.events, key=lambda e: e.ordinal)
    right = sorted(candidate.events, key=lambda e: e.ordinal)
    if len(left) != len(right):
        issues.append(
            FidelityIssue(
                code="event_count",
                ordinal=None,
                message=f"original has {len(left)} events, candidate {len(right)}",
            )
        )
    left_pos = {e.native_id: i for i, e in enumerate(left)}
    right_pos = {e.native_id: i for i, e in enumerate(right)}
    for index, (a, b) in enumerate(zip(left, right, strict=False)):
        if a.ordinal != b.ordinal:
            issues.append(
                FidelityIssue(
                    code="ordinal",
                    ordinal=a.ordinal,
                    message=f"event {index} ordinal {a.ordinal} became {b.ordinal}",
                )
            )
        parent_a = left_pos.get(a.parent_id) if a.parent_id is not None else None
        parent_b = right_pos.get(b.parent_id) if b.parent_id is not None else None
        if parent_a != parent_b:
            issues.append(
                FidelityIssue(
                    code="parent",
                    ordinal=a.ordinal,
                    message=f"event {index} parent position {parent_a} became {parent_b}",
                )
            )
        if a.kind != b.kind:
            issues.append(
                FidelityIssue(
                    code="kind",
                    ordinal=a.ordinal,
                    message=f"event {index} kind {a.kind} became {b.kind}",
                )
            )
        if a.role != b.role:
            issues.append(
                FidelityIssue(
                    code="role",
                    ordinal=a.ordinal,
                    message=f"event {index} role {a.role} became {b.role}",
                )
            )
        kinds_a = [block.kind for block in a.content]
        kinds_b = [block.kind for block in b.content]
        if kinds_a != kinds_b:
            issues.append(
                FidelityIssue(
                    code="block_kinds",
                    ordinal=a.ordinal,
                    message=f"event {index} blocks {kinds_a} became {kinds_b}",
                )
            )
        else:
            captured_a = [block.text is not None for block in a.content]
            captured_b = [block.text is not None for block in b.content]
            if captured_a != captured_b:
                issues.append(
                    FidelityIssue(
                        code="text_captured",
                        ordinal=a.ordinal,
                        message=f"event {index} changes which blocks have captured text",
                    )
                )
        if set(a.extensions) != set(b.extensions) or any(
            set(x.extensions) != set(y.extensions)
            for x, y in zip(a.content, b.content, strict=False)
        ):
            issues.append(
                FidelityIssue(
                    code="extension_keys",
                    ordinal=a.ordinal,
                    message=f"event {index} changes extension keys",
                )
            )
    if _tool_pairing(left) != _tool_pairing(right):
        issues.append(
            FidelityIssue(
                code="tool_pairing",
                ordinal=None,
                message="tool_call/tool_result pairing differs between the two",
            )
        )
    kinds_left = sorted(str(r.get("kind")) for r in original.relationships)
    kinds_right = sorted(str(r.get("kind")) for r in candidate.relationships)
    if kinds_left != kinds_right:
        issues.append(
            FidelityIssue(
                code="relationship_kinds",
                ordinal=None,
                message=f"relationships {kinds_left} became {kinds_right}",
            )
        )
    return issues


def _tool_pairing(events: Sequence[FixtureEvent]) -> list[tuple[str, ...]]:
    """Each tool_call_id as the sorted set of (event index, block index, kind)."""
    groups: dict[str, list[str]] = {}
    for event_index, event in enumerate(events):
        for block_index, block in enumerate(event.content):
            if block.kind in {"tool_call", "tool_result"} and block.tool_call_id:
                groups.setdefault(block.tool_call_id, []).append(
                    f"{event_index}:{block_index}:{block.kind}"
                )
    return sorted(tuple(sorted(group)) for group in groups.values())


def _strings(value: Any, location: str) -> Iterable[tuple[str, str]]:
    if isinstance(value, str):
        yield location, value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from _strings(item, f"{location}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _strings(item, f"{location}[{index}]")


def leak_issues(
    candidate: FixtureConversation,
    *,
    terms: Sequence[str],
    originals: dict[str, ScrubCategory],
) -> list[LeakIssue]:
    """Find operator terms or scrubbed original text anywhere in a candidate."""
    issues: list[LeakIssue] = []
    term_pattern = _term_pattern(terms)
    spans = sorted(
        (s for s, c in originals.items() if len(s) >= 3 and c != "term"),
        key=len,
        reverse=True,
    )
    for location, text in _strings(candidate.model_dump(mode="python"), "candidate"):
        if term_pattern is not None:
            for match in term_pattern.finditer(text):
                issues.append(
                    LeakIssue(
                        code="term",
                        location=location,
                        text_start=match.start(),
                        text_end=match.end(),
                        category="term",
                    )
                )
        folded = text.casefold()
        for span in spans:
            needle = span.casefold()
            start = folded.find(needle)
            while start != -1:
                issues.append(
                    LeakIssue(
                        code="original_span",
                        location=location,
                        text_start=start,
                        text_end=start + len(needle),
                        category=originals[span],
                    )
                )
                start = folded.find(needle, start + 1)
    return issues
