"""Strict, side-effect-free validation for normalized conversation v1.

This module validates serialized conversation data only. It neither reads retained
snapshots nor follows artifact locators or relationship targets.
"""

from __future__ import annotations

import datetime as _datetime
import json
import math
from typing import NoReturn, cast


class ConversationValidationError(ValueError):
    """Raised when a normalized conversation is structurally invalid.

    Messages contain only a bounded field path and never serialized content.
    """


def _invalid(path: str) -> NoReturn:
    raise ConversationValidationError(f"invalid field: {path}")


def _is_string(value: object) -> bool:
    return isinstance(value, str)


def _nonempty_string(value: object, path: str) -> str:
    if not _is_string(value) or not value:
        _invalid(path)
    return cast(str, value)


def _integer(value: object, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        _invalid(path)
    return value


def _object(value: object, path: str) -> dict[str, object]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        _invalid(path)
    return value


def _list(value: object, path: str) -> list[object]:
    if not isinstance(value, list):
        _invalid(path)
    return value


def _nullable_nonempty_string(value: object, path: str) -> None:
    if value is not None:
        _nonempty_string(value, path)


def _json_value(
    value: object, path: str, active_containers: set[int] | None = None
) -> None:
    """Validate values accepted by strict JSON, recursively."""
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            _invalid(path)
        return
    if not isinstance(value, (list, dict)):
        _invalid(path)

    if active_containers is None:
        active_containers = set()
    marker = id(value)
    if marker in active_containers:
        _invalid(path)
    active_containers.add(marker)
    try:
        if isinstance(value, list):
            for index, item in enumerate(value):
                _json_value(item, f"{path}[{index}]", active_containers)
        else:
            for key, item in value.items():
                if not isinstance(key, str):
                    _invalid(path)
                _json_value(item, f"{path}.*", active_containers)
    except RecursionError:
        _invalid(path)
    finally:
        active_containers.remove(marker)


def _strict_object(value: object, path: str, required: set[str]) -> dict[str, object]:
    result = _object(value, path)
    if set(result) != required:
        _invalid(path)
    return result


def _timestamp(value: object, path: str) -> None:
    if not isinstance(value, str) or "T" not in value:
        _invalid(path)
    try:
        parsed = _datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        _invalid(path)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        _invalid(path)


def _extensions(value: object, path: str) -> None:
    _json_value(_object(value, path), path)


def _coverage(value: object, path: str) -> dict[str, object]:
    coverage = _object(value, path)
    states = {"available", "partial", "unavailable", "unknown", "redacted"}
    for name, state in coverage.items():
        if (
            not isinstance(name, str)
            or not name
            or not isinstance(state, str)
            or state not in states
        ):
            _invalid(path)
    return coverage


def _validate_source(value: object) -> None:
    source = _strict_object(
        value,
        "source",
        {
            "kind",
            "scope_id",
            "native_id",
            "adapter_version",
            "source_version",
            "captured_at",
            "snapshot_id",
            "extensions",
        },
    )
    for key in ("kind", "scope_id", "native_id", "adapter_version", "snapshot_id"):
        _nonempty_string(source[key], f"source.{key}")
    _nullable_nonempty_string(source["source_version"], "source.source_version")
    _timestamp(source["captured_at"], "source.captured_at")
    _extensions(source["extensions"], "source.extensions")


def _validate_artifacts(value: object) -> set[str]:
    artifacts = _list(value, "artifacts")
    identifiers: set[str] = set()
    states = {"available", "partial", "unavailable", "unknown", "redacted"}
    required = {"id", "kind", "media_type", "availability", "locator", "extensions"}
    for index, item in enumerate(artifacts):
        path = f"artifacts[{index}]"
        artifact = _strict_object(item, path, required)
        artifact_id = _nonempty_string(artifact["id"], f"{path}.id")
        if artifact_id in identifiers:
            _invalid(f"{path}.id")
        identifiers.add(artifact_id)
        _nonempty_string(artifact["kind"], f"{path}.kind")
        _nullable_nonempty_string(artifact["media_type"], f"{path}.media_type")
        availability = artifact["availability"]
        if not isinstance(availability, str) or availability not in states:
            _invalid(f"{path}.availability")
        _nullable_nonempty_string(artifact["locator"], f"{path}.locator")
        if availability == "available" and artifact["locator"] is None:
            _invalid(f"{path}.locator")
        _extensions(artifact["extensions"], f"{path}.extensions")
    return identifiers


def _validate_relationships(value: object) -> None:
    relationships = _list(value, "relationships")
    required = {
        "kind",
        "target_source_kind",
        "target_source_scope_id",
        "target_native_id",
        "extensions",
    }
    kinds = {"branch", "continuation", "derived_from", "unknown"}
    for index, item in enumerate(relationships):
        path = f"relationships[{index}]"
        relationship = _strict_object(item, path, required)
        if (
            not isinstance(relationship["kind"], str)
            or relationship["kind"] not in kinds
        ):
            _invalid(f"{path}.kind")
        for key in ("target_source_kind", "target_source_scope_id", "target_native_id"):
            _nonempty_string(relationship[key], f"{path}.{key}")
        _extensions(relationship["extensions"], f"{path}.extensions")


def _validate_metadata(value: object) -> None:
    metadata = _list(value, "metadata")
    required = {
        "name",
        "value",
        "origin",
        "producer",
        "producer_version",
        "input_revision",
        "extensions",
    }
    origins = {"imported", "calculated", "generated", "human"}
    for index, item in enumerate(metadata):
        path = f"metadata[{index}]"
        entry = _strict_object(item, path, required)
        _nonempty_string(entry["name"], f"{path}.name")
        _json_value(entry["value"], f"{path}.value")
        if not isinstance(entry["origin"], str) or entry["origin"] not in origins:
            _invalid(f"{path}.origin")
        _nonempty_string(entry["producer"], f"{path}.producer")
        _nullable_nonempty_string(entry["producer_version"], f"{path}.producer_version")
        _nonempty_string(entry["input_revision"], f"{path}.input_revision")
        _extensions(entry["extensions"], f"{path}.extensions")


def _validate_events(
    value: object, artifact_ids: set[str], coverage: dict[str, object]
) -> None:
    events = _list(value, "events")
    required = {
        "id",
        "native_id",
        "ordinal",
        "parent_id",
        "kind",
        "role",
        "occurred_at",
        "content",
        "extensions",
    }
    event_ids: set[str] = set()
    native_ids: set[str] = set()
    ordinals: set[int] = set()
    parsed: list[tuple[dict[str, object], str]] = []
    previous_ordinal = -1
    for index, item in enumerate(events):
        path = f"events[{index}]"
        event = _strict_object(item, path, required)
        event_id = _nonempty_string(event["id"], f"{path}.id")
        native_id = _nonempty_string(event["native_id"], f"{path}.native_id")
        if event_id in event_ids or native_id in native_ids:
            _invalid(path)
        event_ids.add(event_id)
        native_ids.add(native_id)
        ordinal = _integer(event["ordinal"], f"{path}.ordinal")
        if ordinal < 0 or ordinal in ordinals or ordinal <= previous_ordinal:
            _invalid(f"{path}.ordinal")
        ordinals.add(ordinal)
        previous_ordinal = ordinal
        _nullable_nonempty_string(event["parent_id"], f"{path}.parent_id")
        if not isinstance(event["kind"], str) or event["kind"] not in {
            "message",
            "compaction",
            "configuration",
            "unknown",
        }:
            _invalid(f"{path}.kind")
        if not isinstance(event["role"], str) or event["role"] not in {
            "system",
            "developer",
            "user",
            "assistant",
            "tool",
            "unknown",
        }:
            _invalid(f"{path}.role")
        if event["occurred_at"] is not None:
            _timestamp(event["occurred_at"], f"{path}.occurred_at")
        _extensions(event["extensions"], f"{path}.extensions")
        parsed.append((event, path))

    by_id = {cast(str, event["id"]): event for event, _ in parsed}
    for event, path in parsed:
        parent_id = event["parent_id"]
        if parent_id is not None:
            parent = by_id.get(cast(str, parent_id))
            if parent is None or cast(int, parent["ordinal"]) >= cast(
                int, event["ordinal"]
            ):
                _invalid(f"{path}.parent_id")

    # Parent ordinals are strictly lower, so following parents always terminates.
    # The explicit walk retains a clear cycle guard for programmatic input.
    for event, path in parsed:
        seen: set[str] = set()
        current = event
        while current["parent_id"] is not None:
            current_id = cast(str, current["id"])
            if current_id in seen:
                _invalid(f"{path}.parent_id")
            seen.add(current_id)
            parent = by_id.get(cast(str, current["parent_id"]))
            if parent is None:
                _invalid(f"{path}.parent_id")
            current = parent

    calls_by_event: dict[str, set[str]] = {}
    for event, path in parsed:
        inherited: set[str] = set()
        parent_id = event["parent_id"]
        if parent_id is not None:
            inherited.update(calls_by_event[cast(str, parent_id)])
        calls = set(inherited)
        block_ids: set[str] = set()
        content = _list(event["content"], f"{path}.content")
        for block_index, item in enumerate(content):
            block_path = f"{path}.content[{block_index}]"
            block = _strict_object(
                item,
                block_path,
                {"id", "kind", "text", "tool_call_id", "artifact_id", "extensions"},
            )
            block_id = _nonempty_string(block["id"], f"{block_path}.id")
            if block_id in block_ids:
                _invalid(f"{block_path}.id")
            block_ids.add(block_id)
            if not isinstance(block["kind"], str) or block["kind"] not in {
                "text",
                "reasoning",
                "tool_call",
                "tool_result",
                "attachment",
                "unknown",
            }:
                _invalid(f"{block_path}.kind")
            if block["text"] is not None and not isinstance(block["text"], str):
                _invalid(f"{block_path}.text")
            _nullable_nonempty_string(
                block["tool_call_id"], f"{block_path}.tool_call_id"
            )
            _nullable_nonempty_string(block["artifact_id"], f"{block_path}.artifact_id")
            _extensions(block["extensions"], f"{block_path}.extensions")
            if (
                block["kind"] in {"tool_call", "tool_result"}
                and block["tool_call_id"] is None
            ):
                _invalid(f"{block_path}.tool_call_id")
            if (
                block["artifact_id"] is not None
                and block["artifact_id"] not in artifact_ids
            ):
                _invalid(f"{block_path}.artifact_id")
            if block["kind"] == "attachment" and block["artifact_id"] is None:
                _invalid(f"{block_path}.artifact_id")
            if block["kind"] == "tool_result" and block["tool_call_id"] not in calls:
                if coverage.get("tool_calls") not in {
                    "partial",
                    "unknown",
                    "unavailable",
                    "redacted",
                }:
                    _invalid(f"{block_path}.tool_call_id")
            if block["kind"] == "tool_call":
                call_id = cast(str, block["tool_call_id"])
                if call_id in calls:
                    _invalid(f"{block_path}.tool_call_id")
                calls.add(call_id)
        calls_by_event[cast(str, event["id"])] = calls


def validate_conversation(document: object) -> None:
    """Validate a normalized conversation v1 without mutating it."""
    envelope = _strict_object(
        document,
        "document",
        {
            "schema_version",
            "id",
            "revision",
            "source",
            "events",
            "artifacts",
            "relationships",
            "metadata",
            "coverage",
            "extensions",
        },
    )
    _integer(envelope["schema_version"], "schema_version")
    if envelope["schema_version"] != 1:
        _invalid("schema_version")
    _nonempty_string(envelope["id"], "id")
    _nonempty_string(envelope["revision"], "revision")
    _validate_source(envelope["source"])
    coverage = _coverage(envelope["coverage"], "coverage")
    artifact_ids = _validate_artifacts(envelope["artifacts"])
    _validate_events(envelope["events"], artifact_ids, coverage)
    _validate_relationships(envelope["relationships"])
    _validate_metadata(envelope["metadata"])
    _extensions(envelope["extensions"], "extensions")


def _reject_constant(_: str) -> NoReturn:
    _invalid("json")


def _no_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            _invalid("json")
        result[key] = value
    return result


def load_conversation_json(text: str) -> dict[str, object]:
    """Load and validate one strict JSON normalized conversation."""
    if not isinstance(text, str):
        _invalid("json")
    try:
        document = json.loads(
            text, object_pairs_hook=_no_duplicate_keys, parse_constant=_reject_constant
        )
    except (json.JSONDecodeError, RecursionError, TypeError, ValueError) as error:
        if isinstance(error, ConversationValidationError):
            raise
        _invalid("json")
    if not isinstance(document, dict):
        _invalid("document")
    validate_conversation(document)
    return document


def dump_conversation_json(document: object) -> str:
    """Validate and serialize one conversation with stable strict JSON."""
    validate_conversation(document)
    try:
        return json.dumps(
            document, allow_nan=False, sort_keys=True, separators=(",", ":")
        )
    except (TypeError, ValueError, RecursionError):
        _invalid("document")
