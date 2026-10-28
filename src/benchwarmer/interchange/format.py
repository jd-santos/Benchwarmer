"""The Benchwarmer conversation file, format version 1.

One JSON document per conversation, written by any system that wants its
conversations in the library. The writer supplies native identities, events,
content blocks, and whatever it knows about tools, provenance, context,
feedback, and raw payloads; Benchwarmer assigns library ids and the revision
hash on import. ``docs/conversation-interchange.md`` is the reference and
``docs/schemas/conversation-file.v1.schema.json`` the JSON Schema; this module
is the validator and the converter to the shared ``FileConversation`` form.

Validation here collects every structural issue with its JSON path so a writer
can fix a file in one pass. Issues never quote the file's content.
"""

from __future__ import annotations

from dataclasses import dataclass
import datetime as dt
import json
import math
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from benchwarmer.adapters.file_conversations import (
    FileConversation,
    block,
    document_for,
    event,
)
from benchwarmer.conversations import ConversationValidationError

FORMAT = "benchwarmer-conversation-file"
FORMAT_VERSION = 1
SOURCE_KIND = "conversation_file"
ADAPTER_VERSION = "1"
MAX_IDENTIFIER = 255

EVENT_KINDS = ("message", "configuration", "compaction", "unknown")
ROLES = ("system", "developer", "user", "assistant", "tool", "unknown")
BLOCK_KINDS = ("text", "reasoning", "tool_call", "tool_result", "attachment", "unknown")
COVERAGE_STATES = ("available", "partial", "unavailable", "unknown", "redacted")
RELATIONSHIP_KINDS = ("branch", "continuation", "derived_from", "unknown")
# Metadata names Benchwarmer derives itself; a writer's entry would collide.
RESERVED_METADATA_NAMES = frozenset({"annotation", "usage_observations", "title"})
# Extension keys Benchwarmer fills from typed fields; see conversations.py.
RESERVED_EVENT_EXTENSIONS = frozenset({"provenance", "supersedes_native_id"})
RESERVED_BLOCK_EXTENSIONS = frozenset({"tool_call", "tool_result"})
RESERVED_DOCUMENT_EXTENSIONS = frozenset({"tool_definitions"})

_TOP_LEVEL = {
    "format",
    "format_version",
    "scope_id",
    "native_id",
    "source_version",
    "title",
    "events",
    "tools",
    "context",
    "annotations",
    "relationships",
    "metadata",
    "coverage",
    "extensions",
    "native",
}
_EVENT_KEYS = {
    "native_id",
    "parent_native_id",
    "kind",
    "role",
    "occurred_at",
    "content",
    "provenance",
    "supersedes_native_id",
    "extensions",
}
_BLOCK_KEYS = {
    "kind",
    "text",
    "tool_call_id",
    "tool_name",
    "input",
    "output",
    "is_error",
    "context_id",
    "extensions",
}
_PROVENANCE_KEYS = {"model", "provider", "params", "system_prompt_sha256", "usage"}
_TOOL_KEYS = {"name", "description", "input_schema"}
_CONTEXT_KEYS = {"id", "kind", "name", "media_type", "text"}
_ANNOTATION_KEYS = {"kind", "event_native_id", "rating", "text", "by", "at"}
_RELATIONSHIP_KEYS = {
    "kind",
    "target_scope_id",
    "target_native_id",
    "target_source_kind",
}
_SHA256 = frozenset("0123456789abcdef")


class ConversationFileError(ValueError):
    """A conversation file is not valid; ``issues`` says where."""

    def __init__(self, issues: list[Issue]) -> None:
        shown = ", ".join(issue.path for issue in issues[:5])
        more = f" (+{len(issues) - 5} more)" if len(issues) > 5 else ""
        super().__init__(f"conversation file is invalid at {shown}{more}")
        self.issues = issues


@dataclass(frozen=True, slots=True)
class Issue:
    """One validation finding: a JSON path into the file and a bounded message."""

    path: str
    message: str


class _Collector:
    def __init__(self) -> None:
        self.issues: list[Issue] = []

    def add(self, path: str, message: str) -> None:
        self.issues.append(Issue(path, message))

    def string(
        self,
        value: object,
        path: str,
        *,
        nonempty: bool = True,
        nullable: bool = False,
        max_length: int | None = None,
    ) -> bool:
        if value is None:
            if nullable:
                return True
            self.add(path, "must be a string")
            return False
        if not isinstance(value, str):
            self.add(path, "must be a string")
            return False
        if nonempty and not value:
            self.add(path, "must not be empty")
            return False
        if max_length is not None and len(value) > max_length:
            self.add(path, f"must be at most {max_length} characters")
            return False
        return True

    def object(self, value: object, path: str) -> dict[str, Any] | None:
        if not isinstance(value, dict):
            self.add(path, "must be an object")
            return None
        return value

    def keys(
        self, value: dict[str, Any], path: str, allowed: set[str], required: set[str]
    ) -> bool:
        ok = True
        for key in sorted(set(value) - allowed):
            self.add(f"{path}.{key}", "is not a recognized field")
            ok = False
        for key in sorted(required - set(value)):
            self.add(f"{path}.{key}", "is required")
            ok = False
        return ok

    def array(self, value: object, path: str) -> list[Any] | None:
        if not isinstance(value, list):
            self.add(path, "must be an array")
            return None
        return value

    def json_value(self, value: object, path: str) -> None:
        if value is None or isinstance(value, (str, bool, int)):
            return
        if isinstance(value, float):
            if not math.isfinite(value):
                self.add(path, "must be a finite number")
            return
        if isinstance(value, list):
            for index, item in enumerate(value):
                self.json_value(item, f"{path}[{index}]")
            return
        if isinstance(value, dict):
            for key, item in value.items():
                if not isinstance(key, str):
                    self.add(path, "object keys must be strings")
                    continue
                self.json_value(item, f"{path}.{key}")
            return
        self.add(path, "is not a JSON value")

    def timestamp(self, value: object, path: str) -> None:
        if value is None:
            return
        if not isinstance(value, str) or "T" not in value:
            self.add(path, "must be an RFC 3339 timestamp with a UTC offset")
            return
        try:
            parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            self.add(path, "must be an RFC 3339 timestamp with a UTC offset")
            return
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            self.add(path, "must carry a UTC offset")

    def choice(self, value: object, path: str, choices: tuple[str, ...]) -> bool:
        if not isinstance(value, str) or value not in choices:
            self.add(path, "must be one of " + ", ".join(choices))
            return False
        return True

    def extensions(self, value: object, path: str, reserved: frozenset[str]) -> None:
        extensions = self.object(value, path)
        if extensions is None:
            return
        for key in sorted(set(extensions) & reserved):
            self.add(f"{path}.{key}", "is reserved; use the typed field instead")
        self.json_value(extensions, path)


def _validate_provenance(found: _Collector, value: object, path: str) -> None:
    provenance = found.object(value, path)
    if provenance is None:
        return
    if not found.keys(provenance, path, _PROVENANCE_KEYS, {"model"}):
        return
    found.string(provenance["model"], f"{path}.model")
    if "provider" in provenance:
        found.string(provenance["provider"], f"{path}.provider", nullable=True)
    if "params" in provenance:
        params = found.object(provenance["params"], f"{path}.params")
        if params is not None:
            found.json_value(params, f"{path}.params")
    digest = provenance.get("system_prompt_sha256")
    if digest is not None and (
        not isinstance(digest, str) or len(digest) != 64 or not set(digest) <= _SHA256
    ):
        found.add(f"{path}.system_prompt_sha256", "must be 64 lowercase hex characters")
    if "usage" in provenance:
        usage = found.object(provenance["usage"], f"{path}.usage")
        if usage is not None:
            found.json_value(usage, f"{path}.usage")


def _validate_block(
    found: _Collector, value: object, path: str, context_ids: set[str]
) -> None:
    item = found.object(value, path)
    if item is None:
        return
    if not found.keys(item, path, _BLOCK_KEYS, {"kind"}):
        return
    if not found.choice(item["kind"], f"{path}.kind", BLOCK_KINDS):
        return
    kind = item["kind"]
    found.string(item.get("text"), f"{path}.text", nonempty=False, nullable=True)
    if kind in {"tool_call", "tool_result"}:
        if "tool_call_id" not in item:
            found.add(f"{path}.tool_call_id", "is required for tool blocks")
        else:
            found.string(item["tool_call_id"], f"{path}.tool_call_id")
    elif item.get("tool_call_id") is not None:
        found.add(f"{path}.tool_call_id", "applies to tool_call and tool_result only")
    if kind == "tool_call":
        if "tool_name" in item:
            found.string(item["tool_name"], f"{path}.tool_name", nullable=True)
        if "input" in item:
            if item.get("tool_name") is None:
                found.add(f"{path}.input", "needs tool_name")
            found.json_value(item["input"], f"{path}.input")
    else:
        for key in ("tool_name", "input"):
            if key in item:
                found.add(f"{path}.{key}", "applies to tool_call blocks only")
    if kind == "tool_result":
        if "output" in item:
            found.json_value(item["output"], f"{path}.output")
        if "is_error" in item and not isinstance(item["is_error"], bool):
            found.add(f"{path}.is_error", "must be a boolean")
    else:
        for key in ("output", "is_error"):
            if key in item:
                found.add(f"{path}.{key}", "applies to tool_result blocks only")
    if kind == "attachment":
        context_id = item.get("context_id")
        if "context_id" not in item:
            found.add(f"{path}.context_id", "is required for attachment blocks")
        elif found.string(context_id, f"{path}.context_id"):
            if context_id not in context_ids:
                found.add(f"{path}.context_id", "names no context item")
    elif "context_id" in item:
        found.add(f"{path}.context_id", "applies to attachment blocks only")
    if "extensions" in item:
        found.extensions(
            item["extensions"], f"{path}.extensions", RESERVED_BLOCK_EXTENSIONS
        )


def _validate_events(
    found: _Collector, value: object, context_ids: set[str]
) -> set[str]:
    events = found.array(value, "$.events")
    native_ids: set[str] = set()
    if events is None:
        return native_ids
    if not events:
        found.add("$.events", "must contain at least one event")
    for index, raw in enumerate(events):
        path = f"$.events[{index}]"
        item = found.object(raw, path)
        if item is None:
            continue
        if not found.keys(item, path, _EVENT_KEYS, {"native_id", "role", "content"}):
            continue
        native_id = item["native_id"]
        if found.string(native_id, f"{path}.native_id", max_length=MAX_IDENTIFIER):
            if native_id in native_ids:
                found.add(f"{path}.native_id", "repeats an earlier native_id")
        parent = item.get("parent_native_id")
        if parent is not None:
            if found.string(parent, f"{path}.parent_native_id"):
                if parent not in native_ids:
                    found.add(
                        f"{path}.parent_native_id",
                        "must name an earlier event in the file",
                    )
        superseded = item.get("supersedes_native_id")
        if superseded is not None:
            if found.string(superseded, f"{path}.supersedes_native_id"):
                if superseded not in native_ids:
                    found.add(
                        f"{path}.supersedes_native_id",
                        "must name an earlier event in the file",
                    )
        if "kind" in item:
            found.choice(item["kind"], f"{path}.kind", EVENT_KINDS)
        found.choice(item["role"], f"{path}.role", ROLES)
        found.timestamp(item.get("occurred_at"), f"{path}.occurred_at")
        content = found.array(item["content"], f"{path}.content")
        if content is not None:
            for block_index, raw_block in enumerate(content):
                _validate_block(
                    found,
                    raw_block,
                    f"{path}.content[{block_index}]",
                    context_ids,
                )
        if item.get("provenance") is not None:
            _validate_provenance(found, item["provenance"], f"{path}.provenance")
        if "extensions" in item:
            found.extensions(
                item["extensions"], f"{path}.extensions", RESERVED_EVENT_EXTENSIONS
            )
        if isinstance(native_id, str):
            native_ids.add(native_id)
    return native_ids


def _validate_tools(found: _Collector, value: object) -> None:
    tools = found.array(value, "$.tools")
    if tools is None:
        return
    names: set[str] = set()
    for index, raw in enumerate(tools):
        path = f"$.tools[{index}]"
        item = found.object(raw, path)
        if item is None or not found.keys(item, path, _TOOL_KEYS, {"name"}):
            continue
        if found.string(item["name"], f"{path}.name"):
            if item["name"] in names:
                found.add(f"{path}.name", "repeats an earlier tool name")
            names.add(item["name"])
        if "description" in item:
            found.string(
                item["description"],
                f"{path}.description",
                nonempty=False,
                nullable=True,
            )
        schema = item.get("input_schema")
        if schema is not None:
            if found.object(schema, f"{path}.input_schema") is not None:
                found.json_value(schema, f"{path}.input_schema")


def _validate_context(found: _Collector, value: object) -> set[str]:
    ids: set[str] = set()
    items = found.array(value, "$.context")
    if items is None:
        return ids
    for index, raw in enumerate(items):
        path = f"$.context[{index}]"
        item = found.object(raw, path)
        if item is None or not found.keys(item, path, _CONTEXT_KEYS, {"id"}):
            continue
        if found.string(item["id"], f"{path}.id", max_length=MAX_IDENTIFIER):
            if item["id"] in ids:
                found.add(f"{path}.id", "repeats an earlier context id")
            ids.add(item["id"])
        for key in ("kind", "media_type"):
            if key in item:
                found.string(item[key], f"{path}.{key}", nullable=True)
        for key in ("name", "text"):
            if key in item:
                found.string(item[key], f"{path}.{key}", nonempty=False, nullable=True)
    return ids


def _validate_annotations(
    found: _Collector, value: object, native_ids: set[str]
) -> None:
    items = found.array(value, "$.annotations")
    if items is None:
        return
    for index, raw in enumerate(items):
        path = f"$.annotations[{index}]"
        item = found.object(raw, path)
        if item is None or not found.keys(item, path, _ANNOTATION_KEYS, {"kind"}):
            continue
        found.string(item["kind"], f"{path}.kind")
        target = item.get("event_native_id")
        if target is not None and found.string(target, f"{path}.event_native_id"):
            if target not in native_ids:
                found.add(f"{path}.event_native_id", "names no event in the file")
        rating = item.get("rating")
        if rating is not None and (
            isinstance(rating, bool) or not isinstance(rating, (str, int))
        ):
            found.add(f"{path}.rating", "must be a string or an integer")
        for key in ("text", "by"):
            if key in item:
                found.string(item[key], f"{path}.{key}", nonempty=False, nullable=True)
        found.timestamp(item.get("at"), f"{path}.at")


def _validate_relationships(found: _Collector, value: object) -> None:
    items = found.array(value, "$.relationships")
    if items is None:
        return
    required = {"kind", "target_scope_id", "target_native_id"}
    for index, raw in enumerate(items):
        path = f"$.relationships[{index}]"
        item = found.object(raw, path)
        if item is None or not found.keys(item, path, _RELATIONSHIP_KEYS, required):
            continue
        found.choice(item["kind"], f"{path}.kind", RELATIONSHIP_KINDS)
        found.string(item["target_scope_id"], f"{path}.target_scope_id")
        found.string(item["target_native_id"], f"{path}.target_native_id")
        if "target_source_kind" in item:
            found.string(item["target_source_kind"], f"{path}.target_source_kind")


def _validate_metadata(found: _Collector, value: object) -> None:
    items = found.array(value, "$.metadata")
    if items is None:
        return
    for index, raw in enumerate(items):
        path = f"$.metadata[{index}]"
        item = found.object(raw, path)
        if item is None or not found.keys(
            item, path, {"name", "value"}, {"name", "value"}
        ):
            continue
        if found.string(item["name"], f"{path}.name"):
            if item["name"] in RESERVED_METADATA_NAMES:
                found.add(f"{path}.name", "is reserved; Benchwarmer derives it")
        found.json_value(item["value"], f"{path}.value")


def _validate_coverage(found: _Collector, value: object) -> None:
    coverage = found.object(value, "$.coverage")
    if coverage is None:
        return
    for name, state in coverage.items():
        if not name:
            found.add("$.coverage", "dimension names must not be empty")
        found.choice(state, f"$.coverage.{name}", COVERAGE_STATES)


def validate_structure(document: object) -> list[Issue]:
    """Check the file's own shape; see ``validate_conversation_file`` for the whole."""
    found = _Collector()
    root = found.object(document, "$")
    if root is None:
        return found.issues
    found.keys(
        root,
        "$",
        _TOP_LEVEL,
        {"format", "format_version", "scope_id", "native_id", "events"},
    )
    if "format" in root and root["format"] != FORMAT:
        found.add("$.format", f"must be {FORMAT!r}")
    version = root.get("format_version")
    if "format_version" in root and (
        isinstance(version, bool) or version != FORMAT_VERSION
    ):
        found.add("$.format_version", f"must be {FORMAT_VERSION}")
    if "scope_id" in root:
        found.string(root["scope_id"], "$.scope_id", max_length=MAX_IDENTIFIER)
    if "native_id" in root:
        found.string(root["native_id"], "$.native_id", max_length=MAX_IDENTIFIER)
    if "source_version" in root:
        found.string(root["source_version"], "$.source_version", nullable=True)
    if "title" in root:
        found.string(root["title"], "$.title", nonempty=False, nullable=True)
    context_ids: set[str] = set()
    if "context" in root:
        context_ids = _validate_context(found, root["context"])
    if "tools" in root:
        _validate_tools(found, root["tools"])
    native_ids: set[str] = set()
    if "events" in root:
        native_ids = _validate_events(found, root["events"], context_ids)
    if "annotations" in root:
        _validate_annotations(found, root["annotations"], native_ids)
    if "relationships" in root:
        _validate_relationships(found, root["relationships"])
    if "metadata" in root:
        _validate_metadata(found, root["metadata"])
    if "coverage" in root:
        _validate_coverage(found, root["coverage"])
    if "extensions" in root:
        found.extensions(
            root["extensions"], "$.extensions", RESERVED_DOCUMENT_EXTENSIONS
        )
    if "native" in root:
        found.json_value(root["native"], "$.native")
    return found.issues


def validate_conversation_file(document: object) -> list[Issue]:
    """Every issue in a conversation file, structural and semantic.

    Structure is checked first. When it holds, the file is converted and run
    through the normalized conversation validator, which adds the path rules
    (tool results must follow their calls on the same branch unless the
    ``tool_calls`` coverage says capture is partial, and so on). The path in a
    semantic issue points into the file, not the normalized document.
    """
    issues = validate_structure(document)
    if issues:
        return issues
    assert isinstance(document, dict)
    try:
        normalized_preview(document)
    except ConversationValidationError as error:
        field = str(error).removeprefix("invalid field: ")
        issues.append(
            Issue(
                "$." + field if field and not field.startswith("$") else field or "$",
                "rejected by the normalized conversation validator",
            )
        )
    return issues


def _default_coverage(document: dict[str, Any]) -> dict[str, str]:
    events = document["events"]
    has_usage = any(
        isinstance(item.get("provenance"), dict) and "usage" in item["provenance"]
        for item in events
    )
    has_prompt = any(
        item.get("kind") == "configuration" or item["role"] in {"system", "developer"}
        for item in events
    )
    return {
        "messages": "available",
        "branches": "available",
        "usage": "partial" if has_usage else "unknown",
        "prompts": "available" if has_prompt else "unknown",
        # A writer that captured every call and result says so explicitly.
        "tool_calls": "partial",
    }


def _artifact(item: dict[str, Any]) -> dict[str, object]:
    text = item.get("text")
    available = text is not None
    return {
        "id": f"context-{item['id']}",
        "kind": item.get("kind") or "context",
        "media_type": item.get("media_type"),
        "availability": "available" if available else "unavailable",
        # The text sits inside the retained snapshot of this very file.
        "locator": f"context/{item['id']}" if available else None,
        "extensions": {"context_item": {"name": item.get("name"), "text": text}},
    }


def _block(event_id: str, index: int, raw: dict[str, Any]) -> dict[str, object]:
    kind = raw["kind"]
    text = raw.get("text")
    extensions: dict[str, object] = dict(raw.get("extensions") or {})
    artifact_id = None
    if kind == "tool_call":
        name = raw.get("tool_name")
        if text is None and isinstance(name, str):
            text = name
        if name is not None:
            call: dict[str, object] = {"name": name}
            if "input" in raw:
                call["input"] = raw["input"]
            extensions["tool_call"] = call
    elif kind == "tool_result":
        result = {key: raw[key] for key in ("output", "is_error") if key in raw}
        if result:
            extensions["tool_result"] = result
    elif kind == "attachment":
        artifact_id = f"context-{raw['context_id']}"
    built = block(event_id, index, kind, text, tool_call_id=raw.get("tool_call_id"))
    built["artifact_id"] = artifact_id
    built["extensions"] = extensions
    return built


def to_file_conversation(document: dict[str, Any]) -> FileConversation:
    """Convert a structurally valid file to the shared import form.

    The whole file becomes the retained native snapshot, so a writer's raw
    payloads under ``native`` survive alongside the normalized events.
    """
    issues = validate_structure(document)
    if issues:
        raise ConversationFileError(issues)
    events: list[dict[str, object]] = []
    usage: list[dict[str, object]] = []
    for index, raw in enumerate(document["events"]):
        native_id = raw["native_id"]
        extensions: dict[str, object] = dict(raw.get("extensions") or {})
        provenance = raw.get("provenance")
        if provenance is not None:
            extensions["provenance"] = provenance
            if "usage" in provenance:
                usage.append(
                    {
                        "entry_id": native_id,
                        "usage": provenance["usage"],
                        "cost_origin": "imported",
                        "provider": provenance.get("provider"),
                        "model": provenance["model"],
                    }
                )
        if raw.get("supersedes_native_id") is not None:
            extensions["supersedes_native_id"] = raw["supersedes_native_id"]
        events.append(
            event(
                native_id,
                index * 10,
                raw.get("parent_native_id"),
                raw.get("kind", "message"),
                raw["role"],
                raw.get("occurred_at"),
                [_block(native_id, i, part) for i, part in enumerate(raw["content"])],
                extensions,
            )
        )
    metadata: list[tuple[str, object]] = []
    if document.get("title") is not None:
        metadata.append(("title", document["title"]))
    for entry in document.get("metadata") or []:
        metadata.append((entry["name"], entry["value"]))
    if usage:
        metadata.append(("usage_observations", usage))
    extensions: list[tuple[str, object]] = list(
        (document.get("extensions") or {}).items()
    )
    if document.get("tools"):
        extensions.append(
            (
                "tool_definitions",
                [
                    {
                        "name": tool["name"],
                        "description": tool.get("description"),
                        "input_schema": tool.get("input_schema"),
                    }
                    for tool in document["tools"]
                ],
            )
        )
    relationships = tuple(
        {
            "kind": item["kind"],
            "target_source_kind": item.get("target_source_kind") or SOURCE_KIND,
            "target_source_scope_id": item["target_scope_id"],
            "target_native_id": item["target_native_id"],
            "extensions": {},
        }
        for item in document.get("relationships") or []
    )
    annotations = tuple(dict(item) for item in document.get("annotations") or [])
    return FileConversation(
        native_id=document["native_id"],
        native=document,
        events=tuple(events),
        relationships=relationships,
        metadata=tuple(metadata),
        coverage=dict(document["coverage"])
        if document.get("coverage")
        else _default_coverage(document),
        source_version=document.get("source_version"),
        schema_version=FORMAT_VERSION,
        artifacts=tuple(_artifact(item) for item in document.get("context") or []),
        extensions=tuple(extensions),
        annotations=annotations,
    )


def normalized_preview(document: dict[str, Any]) -> dict[str, object]:
    """The normalized conversation this file would import as, with preview ids.

    Library ids depend on the configured source, so the preview uses a stand-in
    source derived from ``scope_id``; events, blocks, artifacts, metadata, and
    coverage are exactly what the import stores.
    """
    item = to_file_conversation(document)
    stub = SimpleNamespace(
        id=f"preview-{document['scope_id']}",
        kind=SOURCE_KIND,
        scope_id=document["scope_id"],
    )
    _, normalized = document_for(
        stub,  # type: ignore[arg-type]
        item,
        "preview-snapshot",
        dt.datetime(1970, 1, 1, tzinfo=dt.UTC),
        ADAPTER_VERSION,
        None,
    )
    return normalized


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate object key")
        result[key] = value
    return result


def _reject_constant(_: str) -> None:
    raise ValueError("non-finite number")


def parse_conversation_file(text: str | bytes) -> dict[str, Any]:
    """Parse strict JSON; duplicate keys and NaN are refused, shape is not checked."""
    try:
        document = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_constant,
        )
    except (ValueError, RecursionError, UnicodeDecodeError) as error:
        raise ConversationFileError([Issue("$", "is not strict JSON")]) from error
    if not isinstance(document, dict):
        raise ConversationFileError([Issue("$", "must be an object")])
    return document


def load_conversation_file(path: Path) -> dict[str, Any]:
    """Read and fully validate one conversation file from disk."""
    document = parse_conversation_file(path.read_bytes())
    issues = validate_conversation_file(document)
    if issues:
        raise ConversationFileError(issues)
    return document
