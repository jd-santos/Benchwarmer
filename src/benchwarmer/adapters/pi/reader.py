"""Read complete Pi v3 JSONL trees without executing Pi or changing its files."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from benchwarmer.adapters.file_conversations import (
    FileConversation,
    FileConversationError,
    FileImportResult,
    block,
    event,
    import_file_conversations,
)
from benchwarmer.config import BenchwarmerSettings

ADAPTER_VERSION = "1"


def _timestamp(value: object) -> str | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            return dt.datetime.fromtimestamp(value / 1000, dt.UTC).isoformat()
        except (ValueError, OverflowError, OSError):
            return None
    if isinstance(value, str):
        try:
            parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed.astimezone(dt.UTC).isoformat() if parsed.tzinfo else None
        except ValueError:
            return None
    return None


def _message_parts(entry_id: str, message: dict[str, Any]) -> list[dict[str, object]]:
    value = message.get("content")
    parts: list[dict[str, object]] = []
    if isinstance(value, str):
        return [block(entry_id, 0, "text", value)]
    if not isinstance(value, list):
        return parts
    for part in value:
        if not isinstance(part, dict):
            continue
        kind = part.get("type")
        text = part.get("text")
        if kind == "text" and isinstance(text, str):
            parts.append(block(entry_id, len(parts), "text", text))
        elif kind == "thinking" and isinstance(part.get("thinking"), str):
            parts.append(block(entry_id, len(parts), "reasoning", part["thinking"]))
        elif kind == "toolCall" and isinstance(part.get("id"), str) and part["id"]:
            parts.append(
                block(
                    entry_id,
                    len(parts),
                    "tool_call",
                    part.get("name") if isinstance(part.get("name"), str) else None,
                    tool_call_id=part["id"],
                )
            )
    if message.get("role") == "toolResult" and isinstance(
        message.get("toolCallId"), str
    ):
        parts.append(
            block(
                entry_id,
                len(parts),
                "tool_result",
                None,
                tool_call_id=message["toolCallId"],
            )
        )
    return parts


def _read_v1_log(rows: list[object]) -> FileConversation:
    """Read the observed run-event log format with calculated ordinal keys."""
    first = rows[0]
    if not isinstance(first, dict):
        raise FileConversationError("Pi log header is invalid")
    run_id = first.get("runId")
    if not isinstance(run_id, str) or not run_id:
        raise FileConversationError("Pi log run identity is invalid")
    events: list[dict[str, object]] = []
    usage: list[dict[str, object]] = []
    for index, row in enumerate(rows, start=1):
        if (
            not isinstance(row, dict)
            or row.get("version") != 1
            or row.get("runId") != run_id
        ):
            raise FileConversationError("Pi log record identity is invalid")
        record_type = row.get("recordType")
        if record_type not in {"message", "tool_start", "tool_end"}:
            raise FileConversationError("Pi log record type is unsupported")
        record_id = f"record-{index}"
        role = row.get("role")
        if role == "toolResult":
            role = "tool"
        elif role not in {"system", "user", "assistant"}:
            role = "unknown"
        value = row.get("text")
        parts = [block(record_id, 0, "text", value)] if isinstance(value, str) else []
        events.append(
            event(
                record_id,
                index * 10,
                f"record-{index - 1}" if index > 1 else None,
                "message" if record_type == "message" else "unknown",
                role,
                _timestamp(row.get("timestamp")) or _timestamp(row.get("ts")),
                parts,
                {
                    "pi_record_type": record_type,
                    "identity_origin": "calculated_ordinal",
                },
            )
        )
        if isinstance(row.get("usage"), dict):
            usage.append(
                {
                    "record_ordinal": index,
                    "usage": row["usage"],
                    "cost_origin": "unknown",
                }
            )
    metadata = (("usage_observations", usage),) if usage else ()
    return FileConversation(
        run_id,
        {"records": rows},
        tuple(events),
        metadata=metadata,
        coverage={
            "messages": "partial",
            "branches": "unknown",
            "usage": "partial" if usage else "unknown",
            "prompts": "unknown",
            "tool_calls": "partial",
        },
        source_version="event-log-v1",
        schema_version=1,
    )


def read_pi_session(path: Path) -> FileConversation:
    """Read one configured Pi session file; malformed or changing files fail closed."""
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise FileConversationError("Pi session path is unusable")
    try:
        before = path.stat()
        raw = path.read_bytes()
        after = path.stat()
    except OSError as error:
        raise FileConversationError("Pi session could not be read") from error
    if (before.st_size, before.st_mtime_ns) != (
        after.st_size,
        after.st_mtime_ns,
    ) or not raw.endswith(b"\n"):
        raise FileConversationError("Pi session is changing or incomplete")
    try:
        rows = [json.loads(line) for line in raw.splitlines()]
    except (ValueError, UnicodeDecodeError) as error:
        raise FileConversationError("Pi session JSONL is invalid") from error
    if not rows or not isinstance(rows[0], dict):
        raise FileConversationError("Pi session header is invalid")
    header = rows[0]
    if header.get("version") == 1 and "recordType" in header:
        return _read_v1_log(rows)
    session_id = header.get("id")
    if (
        header.get("type") != "session"
        or header.get("version") != 3
        or not isinstance(session_id, str)
        or not session_id
    ):
        raise FileConversationError("Pi session format is unsupported")
    entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows[1:]:
        if (
            not isinstance(row, dict)
            or not isinstance(row.get("id"), str)
            or not row["id"]
            or row["id"] in seen
        ):
            raise FileConversationError("Pi entry identity is invalid")
        parent = row.get("parentId")
        if parent is not None and (not isinstance(parent, str) or parent not in seen):
            raise FileConversationError("Pi entry parent is invalid")
        seen.add(row["id"])
        entries.append(row)
    normalized: list[dict[str, object]] = []
    usage: list[dict[str, object]] = []
    for index, row in enumerate(entries, start=1):
        entry_id = row["id"]
        native_type = row.get("type")
        message = row.get("message") if isinstance(row.get("message"), dict) else {}
        native_role = message.get("role")
        role = {
            "user": "user",
            "assistant": "assistant",
            "toolResult": "tool",
            "system": "system",
        }.get(native_role, "unknown")
        kind = (
            "message"
            if native_type == "message"
            else "compaction"
            if native_type in {"compaction", "branch_summary"}
            else "configuration"
            if native_type
            in {"model_change", "thinking_level_change", "session_info", "label"}
            else "unknown"
        )
        parts = _message_parts(entry_id, message) if native_type == "message" else []
        normalized.append(
            event(
                entry_id,
                index * 10,
                row.get("parentId"),
                kind,
                role,
                _timestamp(row.get("timestamp")),
                parts,
                {
                    "pi_entry_type": native_type
                    if isinstance(native_type, str)
                    else "unknown"
                },
            )
        )
        if isinstance(message.get("usage"), dict):
            usage.append(
                {
                    "entry_id": entry_id,
                    "usage": message["usage"],
                    "cost_origin": "calculated",
                    "provider": message.get("provider"),
                    "model": message.get("model"),
                    "response_id": message.get("responseId"),
                }
            )
    # parentSession is a path, not a trustworthy session identity. It remains in
    # the private snapshot until a caller can resolve it within a known scope.
    relationships = ()
    metadata: list[tuple[str, object]] = []
    if usage:
        metadata.append(("usage_observations", usage))
    return FileConversation(
        session_id,
        {"header": header, "entries": entries},
        tuple(normalized),
        relationships,
        tuple(metadata),
        {
            "messages": "available",
            "branches": "available",
            "usage": "partial" if usage else "unknown",
            "prompts": "partial",
            "tool_calls": "partial",
        },
        source_version="session-v3",
        schema_version=3,
    )


def import_pi_session(
    settings: BenchwarmerSettings,
    session: Session,
    *,
    source_id: str,
    path: Path,
    batch_id: str,
    idempotency_key: str,
) -> FileImportResult:
    """Import one Pi session; the caller supplies its enrolled source scope."""
    item = read_pi_session(path)
    return import_file_conversations(
        settings,
        session,
        source_id=source_id,
        source_kind="pi",
        batch_id=batch_id,
        idempotency_key=idempotency_key,
        items=(item,),
        adapter_version=ADAPTER_VERSION,
        source_version="session-v3",
    )


def read_pi_directory(path: Path) -> tuple[FileConversation, ...]:
    """Read all persisted sessions below one explicitly configured Pi directory."""
    if not path.is_absolute() or path.is_symlink() or not path.is_dir():
        raise FileConversationError("Pi session directory is unusable")
    files = sorted(path.rglob("*.jsonl"))
    if not files:
        raise FileConversationError("Pi session directory contains no sessions")
    items = tuple(read_pi_session(file) for file in files)
    if len({item.native_id for item in items}) != len(items):
        raise FileConversationError("Pi session identities are duplicated")
    return items


def import_pi_directory(
    settings: BenchwarmerSettings,
    session: Session,
    *,
    source_id: str,
    path: Path,
    batch_id: str,
    idempotency_key: str,
) -> FileImportResult:
    """Import an explicit Pi session collection with one atomic library batch."""
    items = read_pi_directory(path)
    return import_file_conversations(
        settings,
        session,
        source_id=source_id,
        source_kind="pi",
        batch_id=batch_id,
        idempotency_key=idempotency_key,
        items=items,
        adapter_version=ADAPTER_VERSION,
        source_version="session-v3",
    )
