"""Persist Hermes snapshots and normalized records incrementally."""

from __future__ import annotations

import base64
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
import datetime as dt
import hashlib
import json
import math
import os
import sqlite3
import tempfile
from typing import Callable, cast

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from benchwarmer.config import BenchwarmerSettings
from benchwarmer.conversations import dump_conversation_json, validate_conversation
from benchwarmer.models import (
    ConversationRevision,
    NativeMessage,
    NativeSession,
    NativeSnapshot,
    NativeUsage,
    Source,
    SourceImportState,
    SourcePresence,
)
from benchwarmer.models.import_batch import ImportBatch, ImportCoverage, ImportCursor
from benchwarmer.models.source import utc_now

from .reader import (
    HermesReadError,
    HermesReadRequest,
    HermesReadResult,
    read_hermes_snapshot,
)

_MAX_ERROR_SUMMARY_LENGTH = 2_000


class HermesImportError(ValueError):
    """Report a bounded Hermes import contract failure."""


@dataclass(frozen=True, slots=True)
class _SourceIdentity:
    id: str
    kind: str
    scope_id: str


@dataclass(frozen=True, slots=True)
class HermesImportRequest:
    """Operator-supplied identity and source input for one import attempt."""

    source_id: str
    batch_id: str
    idempotency_key: str
    read_request: HermesReadRequest
    captured_at: dt.datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        for name in ("source_id", "batch_id", "idempotency_key"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise HermesImportError("Hermes import identity is invalid")
        if not isinstance(self.read_request, HermesReadRequest):
            raise HermesImportError("Hermes read request is invalid")
        if self.read_request.database_path is None:
            raise HermesImportError("Hermes read request is invalid")
        if self.captured_at.tzinfo is None or self.captured_at.utcoffset() is None:
            raise HermesImportError("Hermes import timestamp must be UTC-aware")


@dataclass(frozen=True, slots=True)
class HermesImportResult:
    """Bounded outcome and counts from one Hermes import attempt."""

    batch_id: str
    outcome: str
    snapshot_id: str | None
    cursor_after: ImportCursor | None
    sessions: int
    messages: int
    usages: int
    revisions: int
    error_summary: str | None = None


def _json_safe(value: object) -> object:
    """Convert SQLite scalar values into bounded strict-JSON values."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise HermesImportError("Hermes source contains a non-finite value")
        return value
    if isinstance(value, bytes):
        return {"$bytes_base64": base64.b64encode(value).decode("ascii")}
    if isinstance(value, Mapping):
        result: dict[str, object] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise HermesImportError("Hermes source contains an invalid column")
            result[key] = _json_safe(item)
        return result
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    raise HermesImportError("Hermes source contains an unsupported value")


def _safe_row(row: Mapping[str, object]) -> dict[str, object]:
    return cast(dict[str, object], _json_safe(dict(row)))


def _canonical_json(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError, RecursionError) as error:
        raise HermesImportError("Hermes snapshot could not be serialized") from error


def _source_digest(source_id: str) -> str:
    return hashlib.sha256(source_id.encode("utf-8")).hexdigest()[:32]


def _write_private_snapshot(
    settings: BenchwarmerSettings,
    source_id: str,
    payload: bytes,
) -> tuple[str, str, int]:
    """Create or reuse an immutable private snapshot file."""
    settings.initialize()
    digest = hashlib.sha256(payload).hexdigest()
    snapshot_identity = hashlib.sha256(
        source_id.encode("utf-8") + b"\0" + payload
    ).hexdigest()
    snapshot_id = f"hermes-snapshot-{snapshot_identity[:32]}"
    directory = settings.snapshots_dir / "hermes" / _source_digest(source_id)
    # nosemgrep: python.lang.security.audit.insecure-file-permissions.insecure-file-permissions
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    if directory.is_symlink() or not directory.is_dir():
        raise HermesImportError("Hermes snapshot directory is not usable")
    os.chmod(directory, 0o700)
    final_path = directory / f"{digest}.json"

    if final_path.exists():
        if final_path.is_symlink() or not final_path.is_file():
            raise HermesImportError("Hermes snapshot path is not usable")
        if final_path.stat().st_size != len(payload):
            raise HermesImportError("Hermes snapshot content conflicts")
        with final_path.open("rb") as handle:
            if hashlib.sha256(handle.read()).hexdigest() != digest:
                raise HermesImportError("Hermes snapshot content conflicts")
    else:
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=".hermes-snapshot-", dir=directory
        )
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.link(temporary_name, final_path)
        except OSError as error:
            raise HermesImportError("Hermes snapshot could not be written") from error
        finally:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass

    relative_path = final_path.relative_to(settings.data_root).as_posix()
    return snapshot_id, relative_path, len(payload)


def _snapshot_payload(result: HermesReadResult) -> bytes:
    document = {
        "schema_version": 1,
        "application_version": result.application_version,
        "schema_version_observed": result.schema_version,
        "adapter_version": result.adapter_version,
        "capability_manifest_version": result.capability_manifest_version,
        "journal_mode": result.journal_mode,
        "coverage": dict(result.coverage),
        "tables": {
            name: [_safe_row(row) for row in rows]
            for name, rows in sorted(result.tables.items())
        },
    }
    return _canonical_json(document)


def _coverage_summary(result: HermesReadResult) -> ImportCoverage:
    coverage = dict(result.coverage)
    dimensions: dict[str, str] = {
        "schema": "available",
        "journal_mode": "available" if result.journal_mode == "wal" else "unknown",
    }
    for table in (
        "system_prompts",
        "sessions",
        "messages",
        "session_model_usage",
        "gateway_routing",
    ):
        dimensions[table] = coverage.get(f"table.{table}", "unknown")
    dimensions["unknown_columns"] = (
        "partial"
        if any(
            state == "unknown"
            for name, state in coverage.items()
            if name.startswith("column.")
        )
        else "available"
    )
    dimensions["optional_columns"] = (
        "partial"
        if any(
            state == "unavailable"
            for name, state in coverage.items()
            if name.startswith("column.")
        )
        else "available"
    )
    return ImportCoverage(dimensions)


def _cursor_value(cursor: ImportCursor | None) -> tuple[int, int]:
    if cursor is None:
        return 30, 0
    value = cursor.value
    if not isinstance(value, Mapping):
        raise HermesImportError("Hermes import cursor is invalid")
    schema_version = value.get("source_schema_version")
    last_message_id = value.get("last_message_id")
    if (
        type(schema_version) is not int
        or type(last_message_id) is not int
        or schema_version <= 0
        or last_message_id < 0
    ):
        raise HermesImportError("Hermes import cursor is invalid")
    return schema_version, last_message_id


def _new_cursor(
    schema_version: int, last_message_id: int, snapshot_id: str
) -> ImportCursor:
    return ImportCursor(
        {
            "source_schema_version": schema_version,
            "last_message_id": last_message_id,
            "snapshot_id": snapshot_id,
        }
    )


def _required_string(
    row: Mapping[str, object], name: str, *, allow_blank: bool = False
) -> str:
    value = row.get(name)
    if not isinstance(value, str) or (not allow_blank and not value.strip()):
        raise HermesImportError("Hermes source identity is invalid")
    return value


def _required_int(row: Mapping[str, object], name: str) -> int:
    value = row.get(name)
    if type(value) is not int:
        raise HermesImportError("Hermes source identity is invalid")
    return value


def _optional_string(row: Mapping[str, object], name: str) -> str | None:
    value = row.get(name)
    if value is None:
        return None
    if not isinstance(value, str):
        raise HermesImportError("Hermes source payload is invalid")
    return value


def _optional_float(row: Mapping[str, object], name: str) -> float | None:
    value = row.get(name)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise HermesImportError("Hermes source timestamp is invalid")
    try:
        value = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise HermesImportError("Hermes source timestamp is invalid") from error
    if not math.isfinite(value):
        raise HermesImportError("Hermes source timestamp is invalid")
    return value


def _usage_native_id(row: Mapping[str, object]) -> str:
    values = [_required_string(row, name) for name in ("session_id", "model")] + [
        _required_string(row, name, allow_blank=True)
        for name in (
            "billing_provider",
            "billing_base_url",
            "billing_mode",
            "task",
        )
    ]
    return "usage-" + hashlib.sha256("\0".join(values).encode("utf-8")).hexdigest()[:32]


def _iso_timestamp(value: float | None) -> str | None:
    if value is None:
        return None
    try:
        return dt.datetime.fromtimestamp(value, tz=dt.UTC).isoformat()
    except (OverflowError, OSError, ValueError):
        return None


def _role(value: object) -> str:
    if isinstance(value, str) and value in {
        "system",
        "developer",
        "user",
        "assistant",
        "tool",
    }:
        return value
    return "unknown"


def _tool_call_blocks(message: NativeMessage, event_id: str) -> list[dict[str, object]]:
    raw_calls = message.payload.get("tool_calls")
    if isinstance(raw_calls, str):
        try:
            raw_calls = json.loads(raw_calls)
        except (json.JSONDecodeError, RecursionError):
            return []
    if not isinstance(raw_calls, list):
        return []
    blocks: list[dict[str, object]] = []
    for index, raw_call in enumerate(raw_calls):
        if not isinstance(raw_call, Mapping):
            continue
        call_id = raw_call.get("id") or raw_call.get("tool_call_id")
        if not isinstance(call_id, str) or not call_id.strip():
            continue
        name = raw_call.get("name")
        function = raw_call.get("function")
        if not isinstance(name, str) and isinstance(function, Mapping):
            name = function.get("name")
        text = name if isinstance(name, str) else None
        blocks.append(
            {
                "id": f"{event_id}:tool:{index}",
                "kind": "tool_call",
                "text": text,
                "tool_call_id": call_id,
                "artifact_id": None,
                "extensions": {"hermes_tool_call": dict(raw_call)},
            }
        )
    return blocks


def _message_blocks(message: NativeMessage, event_id: str) -> list[dict[str, object]]:
    blocks: list[dict[str, object]] = []
    if message.content is not None:
        blocks.append(
            {
                "id": f"{event_id}:text",
                "kind": "text",
                "text": message.content,
                "tool_call_id": None,
                "artifact_id": None,
                "extensions": {},
            }
        )
    if message.reasoning is not None:
        blocks.append(
            {
                "id": f"{event_id}:reasoning",
                "kind": "reasoning",
                "text": message.reasoning,
                "tool_call_id": None,
                "artifact_id": None,
                "extensions": {},
            }
        )
    tool_call_blocks = _tool_call_blocks(message, event_id)
    if tool_call_blocks:
        blocks.extend(tool_call_blocks)
    elif message.tool_call_id is not None:
        kind = "tool_result" if message.role == "tool" else "tool_call"
        blocks.append(
            {
                "id": f"{event_id}:tool",
                "kind": kind,
                "text": message.tool_name,
                "tool_call_id": message.tool_call_id,
                "artifact_id": None,
                "extensions": {},
            }
        )
    return blocks


def _conversation_document(
    source: _SourceIdentity,
    native_session: NativeSession,
    messages: Sequence[NativeMessage],
    snapshot_id: str,
    result: HermesReadResult,
    captured_at: dt.datetime,
) -> tuple[str, dict[str, object]]:
    conversation_id = (
        "conversation-"
        + hashlib.sha256(
            f"{source.id}\0{native_session.native_id}".encode("utf-8")
        ).hexdigest()[:32]
    )
    events: list[dict[str, object]] = []
    for ordinal, message in enumerate(messages, start=1):
        event_id = f"{conversation_id}:event:{message.native_id}"
        events.append(
            {
                "id": event_id,
                "native_id": message.native_id,
                "ordinal": ordinal * 10,
                "parent_id": events[-1]["id"] if events else None,
                "kind": "message",
                "role": _role(message.role),
                "occurred_at": _iso_timestamp(message.source_timestamp),
                "content": _message_blocks(message, event_id),
                "extensions": {},
            }
        )

    relationships: list[dict[str, object]] = []
    if native_session.parent_native_id is not None:
        relationships.append(
            {
                "kind": "continuation",
                "target_source_kind": source.kind,
                "target_source_scope_id": source.scope_id,
                "target_native_id": native_session.parent_native_id,
                "extensions": {},
            }
        )

    metadata: list[dict[str, object]] = []
    for name, value in (
        ("title", native_session.payload.get("title")),
        ("model", native_session.payload.get("model")),
    ):
        if value is not None:
            metadata.append(
                {
                    "name": name,
                    "value": value,
                    "origin": "imported",
                    "producer": "hermes",
                    "producer_version": result.application_version,
                    "input_revision": snapshot_id,
                    "extensions": {},
                }
            )

    coverage: dict[str, str] = {
        "messages": "available",
        "reasoning": "available"
        if any(message.reasoning is not None for message in messages)
        else "unknown",
        "tool_calls": "partial",
        "prompts": "available"
        if native_session.payload.get("system_prompt") is not None
        else "partial",
        "usage": "available",
    }
    document: dict[str, object] = {
        "schema_version": 1,
        "id": conversation_id,
        "revision": "revision-pending",
        "source": {
            "kind": source.kind,
            "scope_id": source.scope_id,
            "native_id": native_session.native_id,
            "adapter_version": result.adapter_version,
            "source_version": result.application_version
            or f"schema-{result.schema_version}",
            "captured_at": captured_at.isoformat(),
            "snapshot_id": snapshot_id,
            "extensions": {"hermes_schema_version": result.schema_version},
        },
        "events": events,
        "artifacts": [],
        "relationships": relationships,
        "metadata": metadata,
        "coverage": coverage,
        "extensions": {},
    }
    validate_conversation(document)
    revision_basis = dict(document)
    source_basis = dict(cast(dict[str, object], document["source"]))
    source_basis["captured_at"] = "1970-01-01T00:00:00+00:00"
    source_basis["snapshot_id"] = "revision-snapshot"
    revision_basis["source"] = source_basis
    metadata_basis: list[dict[str, object]] = []
    for metadata_entry in cast(list[object], revision_basis["metadata"]):
        metadata_basis.append(dict(cast(dict[str, object], metadata_entry)))
    revision_basis["metadata"] = metadata_basis
    for metadata_entry in metadata_basis:
        metadata_entry["input_revision"] = "revision-input"
    revision = hashlib.sha256(
        dump_conversation_json(revision_basis).encode("utf-8")
    ).hexdigest()
    document["revision"] = revision
    validate_conversation(document)
    return revision, document


def _result_for_existing(session: Session, batch: ImportBatch) -> HermesImportResult:
    snapshot_id: str | None = None
    if batch.cursor_after is not None:
        candidate = batch.cursor_after.value.get("snapshot_id")
        if isinstance(candidate, str):
            snapshot_id = candidate
    result = HermesImportResult(
        batch_id=batch.id,
        outcome=batch.outcome,
        snapshot_id=snapshot_id,
        cursor_after=batch.cursor_after,
        sessions=0,
        messages=0,
        usages=0,
        revisions=0,
        error_summary=batch.error_summary,
    )
    session.rollback()
    return result


def _record_failed(
    session: Session,
    request: HermesImportRequest,
    cursor_before: ImportCursor | None,
    error_summary: str,
    coverage: ImportCoverage | None = None,
) -> HermesImportResult:
    session.rollback()
    now = request.captured_at
    batch = ImportBatch(
        id=request.batch_id,
        source_id=request.source_id,
        idempotency_key=request.idempotency_key,
        outcome="failed",
        cursor_before=cursor_before,
        cursor_after=None,
        observed_coverage=coverage,
        started_at=now,
        completed_at=now,
        error_summary=error_summary[:_MAX_ERROR_SUMMARY_LENGTH],
    )
    try:
        with session.begin():
            session.add(batch)
    except SQLAlchemyError as error:
        raise HermesImportError(
            "Hermes import failure could not be recorded"
        ) from error
    return HermesImportResult(
        batch_id=request.batch_id,
        outcome="failed",
        snapshot_id=None,
        cursor_after=None,
        sessions=0,
        messages=0,
        usages=0,
        revisions=0,
        error_summary=error_summary[:_MAX_ERROR_SUMMARY_LENGTH],
    )


def _persist_snapshot(
    settings: BenchwarmerSettings,
    session: Session,
    source: _SourceIdentity,
    request: HermesImportRequest,
    result: HermesReadResult,
    cursor_before: ImportCursor | None,
) -> HermesImportResult:
    try:
        schema_version, previous_message_id = _cursor_value(cursor_before)
        if cursor_before is not None and schema_version != result.schema_version:
            raise HermesImportError("Hermes schema changed; reconciliation is required")

        message_rows = tuple(result.tables.get("messages", ()))
        message_ids = tuple(_required_int(row, "id") for row in message_rows)
        if any(message_id < 0 for message_id in message_ids):
            raise HermesImportError("Hermes message identity is invalid")
        current_max = max(message_ids, default=0)
        if current_max < previous_message_id:
            raise HermesImportError("Hermes message cursor regressed")
        coverage = _coverage_summary(result)
        raw_payload = _snapshot_payload(result)
        snapshot_id, relative_path, byte_length = _write_private_snapshot(
            settings, source.id, raw_payload
        )
        captured_at = request.captured_at
        new_message_ids = {
            message_id for message_id in message_ids if message_id > previous_message_id
        }
        session_rows = tuple(result.tables.get("sessions", ()))
        usage_rows = tuple(result.tables.get("session_model_usage", ()))
        with session.begin():
            current_state = session.get(SourceImportState, source.id)
            current_cursor = (
                ImportCursor.from_mapping(current_state.cursor)
                if current_state is not None
                else None
            )
            if current_cursor != cursor_before:
                raise HermesImportError("Hermes import cursor changed; retry")
            cursor_after = _new_cursor(result.schema_version, current_max, snapshot_id)
            batch = ImportBatch(
                id=request.batch_id,
                source_id=source.id,
                idempotency_key=request.idempotency_key,
                outcome="succeeded",
                cursor_before=cursor_before,
                cursor_after=cursor_after,
                observed_coverage=coverage,
                started_at=captured_at,
                completed_at=captured_at,
                error_summary=None,
            )
            session.add(batch)
            session.flush()
            snapshot = session.get(NativeSnapshot, snapshot_id)
            if snapshot is None:
                session.add(
                    NativeSnapshot(
                        id=snapshot_id,
                        source_id=source.id,
                        import_batch_id=batch.id,
                        content_sha256=hashlib.sha256(raw_payload).hexdigest(),
                        relative_path=relative_path,
                        byte_length=byte_length,
                        captured_at=captured_at,
                        created_at=captured_at,
                    )
                )
            elif snapshot.source_id != source.id:
                raise HermesImportError("Hermes snapshot identity conflicts")

            for row in session_rows:
                native_id = _required_string(row, "id")
                stored = session.get(
                    NativeSession, {"source_id": source.id, "native_id": native_id}
                )
                payload = _safe_row(row)
                if stored is None:
                    session.add(
                        NativeSession(
                            source_id=source.id,
                            native_id=native_id,
                            parent_native_id=_optional_string(row, "parent_session_id"),
                            source_version=result.application_version
                            or f"schema-{result.schema_version}",
                            schema_version=result.schema_version,
                            application_version=result.application_version,
                            payload=payload,
                            snapshot_id=snapshot_id,
                            source_present=True,
                            first_seen_at=captured_at,
                            last_seen_at=captured_at,
                        )
                    )
                else:
                    stored.parent_native_id = _optional_string(row, "parent_session_id")
                    stored.source_version = (
                        result.application_version or f"schema-{result.schema_version}"
                    )
                    stored.schema_version = result.schema_version
                    stored.application_version = result.application_version
                    stored.payload = payload
                    stored.snapshot_id = snapshot_id
                    stored.source_present = True
                    stored.last_seen_at = captured_at
                session.add(
                    SourcePresence(
                        source_id=source.id,
                        batch_id=batch.id,
                        subject_kind="session",
                        native_id=native_id,
                        present=True,
                        observed_at=captured_at,
                    )
                )

            for row in message_rows:
                native_order = _required_int(row, "id")
                native_id = str(native_order)
                session_native_id = _required_string(row, "session_id")
                stored = session.get(
                    NativeMessage, {"source_id": source.id, "native_id": native_id}
                )
                if stored is None and native_order not in new_message_ids:
                    raise HermesImportError(
                        "Hermes message cursor omitted a source row"
                    )
                if stored is None:
                    stored = NativeMessage(
                        source_id=source.id,
                        native_id=native_id,
                        native_order=native_order,
                        session_native_id=session_native_id,
                        role=_optional_string(row, "role") or "unknown",
                        content=_optional_string(row, "content"),
                        tool_call_id=_optional_string(row, "tool_call_id"),
                        tool_name=_optional_string(row, "tool_name"),
                        reasoning=_optional_string(row, "reasoning"),
                        source_timestamp=_optional_float(row, "timestamp") or 0.0,
                        payload=_safe_row(row),
                        snapshot_id=snapshot_id,
                        source_present=True,
                        first_seen_at=captured_at,
                        last_seen_at=captured_at,
                    )
                    session.add(stored)
                else:
                    stored.native_order = native_order
                    stored.session_native_id = session_native_id
                    stored.role = _optional_string(row, "role") or "unknown"
                    stored.content = _optional_string(row, "content")
                    stored.tool_call_id = _optional_string(row, "tool_call_id")
                    stored.tool_name = _optional_string(row, "tool_name")
                    stored.reasoning = _optional_string(row, "reasoning")
                    stored.source_timestamp = _optional_float(row, "timestamp") or 0.0
                    stored.payload = _safe_row(row)
                    stored.source_present = True
                    stored.snapshot_id = snapshot_id
                    stored.last_seen_at = captured_at
                session.add(
                    SourcePresence(
                        source_id=source.id,
                        batch_id=batch.id,
                        subject_kind="message",
                        native_id=native_id,
                        present=True,
                        observed_at=captured_at,
                    )
                )

            for row in usage_rows:
                session_native_id = _required_string(row, "session_id")
                keys = {
                    "source_id": source.id,
                    "session_native_id": session_native_id,
                    "model": _required_string(row, "model"),
                    "billing_provider": _required_string(
                        row, "billing_provider", allow_blank=True
                    ),
                    "billing_base_url": _required_string(
                        row, "billing_base_url", allow_blank=True
                    ),
                    "billing_mode": _required_string(
                        row, "billing_mode", allow_blank=True
                    ),
                    "task": _required_string(row, "task", allow_blank=True),
                }
                stored = session.get(NativeUsage, keys)
                if stored is None:
                    session.add(
                        NativeUsage(
                            **keys,
                            payload=_safe_row(row),
                            snapshot_id=snapshot_id,
                            source_present=True,
                            first_seen_at=captured_at,
                            last_seen_at=captured_at,
                        )
                    )
                else:
                    stored.payload = _safe_row(row)
                    stored.snapshot_id = snapshot_id
                    stored.source_present = True
                    stored.last_seen_at = captured_at
                session.add(
                    SourcePresence(
                        source_id=source.id,
                        batch_id=batch.id,
                        subject_kind="usage",
                        native_id=_usage_native_id(row),
                        present=True,
                        observed_at=captured_at,
                    )
                )

            session.flush()
            stored_sessions = tuple(
                session.scalars(
                    select(NativeSession).where(NativeSession.source_id == source.id)
                )
            )
            revisions = 0
            for native_session in stored_sessions:
                messages = tuple(
                    session.scalars(
                        select(NativeMessage)
                        .where(
                            NativeMessage.source_id == source.id,
                            NativeMessage.session_native_id == native_session.native_id,
                        )
                        .order_by(NativeMessage.native_order, NativeMessage.native_id)
                    )
                )
                revision, document = _conversation_document(
                    source,
                    native_session,
                    messages,
                    snapshot_id,
                    result,
                    captured_at,
                )
                existing = session.scalar(
                    select(ConversationRevision).where(
                        ConversationRevision.source_id == source.id,
                        ConversationRevision.native_id == native_session.native_id,
                        ConversationRevision.revision == revision,
                    )
                )
                if existing is None:
                    session.add(
                        ConversationRevision(
                            id=f"{document['id']}-{revision[:16]}",
                            source_id=source.id,
                            native_id=native_session.native_id,
                            revision=revision,
                            snapshot_id=snapshot_id,
                            document=document,
                            captured_at=captured_at,
                            created_at=captured_at,
                        )
                    )
                    revisions += 1

            state = session.get(SourceImportState, source.id)
            if state is None:
                session.add(
                    SourceImportState(
                        source_id=source.id,
                        adapter_version=result.adapter_version,
                        schema_version=result.schema_version,
                        cursor=cursor_after.to_storage(),
                        updated_at=captured_at,
                    )
                )
            else:
                state.adapter_version = result.adapter_version
                state.schema_version = result.schema_version
                state.cursor = cursor_after.to_storage()
                state.updated_at = captured_at

        return HermesImportResult(
            batch_id=request.batch_id,
            outcome="succeeded",
            snapshot_id=snapshot_id,
            cursor_after=cursor_after,
            sessions=len(session_rows),
            messages=len(new_message_ids),
            usages=len(usage_rows),
            revisions=revisions,
        )
    except HermesImportError:
        raise
    except (OSError, SQLAlchemyError, sqlite3.Error) as error:
        raise HermesImportError("Hermes import persistence failed") from error


def import_hermes(
    settings: BenchwarmerSettings,
    session: Session,
    request: HermesImportRequest,
    *,
    reader: Callable[[HermesReadRequest], HermesReadResult] = read_hermes_snapshot,
) -> HermesImportResult:
    """Read Hermes once and atomically publish its source and normalized records."""
    if session.in_transaction():
        raise HermesImportError("Hermes import requires an idle database session")
    source = session.get(Source, request.source_id)
    if source is None or source.kind != "hermes":
        raise HermesImportError("configured Hermes source was not found")
    identity = _SourceIdentity(source.id, source.kind, source.scope_id)

    existing = session.scalar(
        select(ImportBatch).where(
            ImportBatch.source_id == request.source_id,
            ImportBatch.idempotency_key == request.idempotency_key,
        )
    )
    if existing is not None:
        return _result_for_existing(session, existing)

    state = session.get(SourceImportState, request.source_id)
    try:
        cursor_before = (
            ImportCursor.from_mapping(state.cursor) if state is not None else None
        )
    except ValueError as error:
        raise HermesImportError("Hermes import cursor is invalid") from error
    session.rollback()
    try:
        result = reader(request.read_request)
    except (HermesReadError, ValueError, OSError, sqlite3.Error) as error:
        del error
        return _record_failed(
            session,
            request,
            cursor_before,
            "Hermes source read failed",
        )

    try:
        return _persist_snapshot(
            settings, session, identity, request, result, cursor_before
        )
    except HermesImportError as error:
        del error
        return _record_failed(
            session,
            request,
            cursor_before,
            "Hermes import failed",
            _coverage_summary(result),
        )
