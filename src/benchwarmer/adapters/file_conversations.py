"""Shared, read-only file-source conversion and private persistence."""

from __future__ import annotations

from dataclasses import dataclass
import datetime as dt
import hashlib
import json
import os
import tempfile
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from benchwarmer.config import BenchwarmerSettings
from benchwarmer.conversations import dump_conversation_json, validate_conversation
from benchwarmer.models import (
    ConversationRevision,
    NativeMessage,
    NativeSession,
    NativeSnapshot,
    Source,
    SourcePresence,
)
from benchwarmer.models.import_batch import ImportBatch, ImportCoverage, ImportCursor
from benchwarmer.models.source import SourceImportState, utc_now


class FileConversationError(ValueError):
    """A bounded source format or persistence failure without private payloads."""


@dataclass(frozen=True, slots=True)
class FileConversation:
    native_id: str
    native: dict[str, Any]
    events: tuple[dict[str, object], ...]
    relationships: tuple[dict[str, object], ...] = ()
    metadata: tuple[tuple[str, object], ...] = ()
    coverage: dict[str, str] | None = None
    source_version: str | None = None
    schema_version: int = 1


@dataclass(frozen=True, slots=True)
class FileImportResult:
    batch_id: str
    conversations: int
    revisions: int
    snapshots: int


def canonical(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, RecursionError) as error:
        raise FileConversationError("source content is not valid JSON") from error


def block(
    event_id: str,
    index: int,
    kind: str,
    text: str | None,
    *,
    tool_call_id: str | None = None,
) -> dict[str, object]:
    return {
        "id": f"{event_id}:block:{index}",
        "kind": kind,
        "text": text,
        "tool_call_id": tool_call_id,
        "artifact_id": None,
        "extensions": {},
    }


def event(
    native_id: str,
    ordinal: int,
    parent_native_id: str | None,
    kind: str,
    role: str,
    occurred_at: str | None,
    content: list[dict[str, object]],
    extensions: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "id": native_id,
        "native_id": native_id,
        "ordinal": ordinal,
        "parent_id": parent_native_id,
        "kind": kind,
        "role": role,
        "occurred_at": occurred_at,
        "content": content,
        "extensions": extensions or {},
    }


def document_for(
    source: Source,
    item: FileConversation,
    snapshot_id: str,
    captured_at: dt.datetime,
    adapter_version: str,
    source_version: str | None,
) -> tuple[str, dict[str, object]]:
    source_version = item.source_version or source_version
    conversation_id = (
        "conversation-"
        + hashlib.sha256(f"{source.id}\0{item.native_id}".encode()).hexdigest()[:32]
    )
    event_ids = {
        str(entry["native_id"]): f"{conversation_id}:event:{entry['native_id']}"
        for entry in item.events
    }
    events: list[dict[str, object]] = []
    for entry in item.events:
        copied = dict(entry)
        copied["id"] = event_ids[str(entry["native_id"])]
        parent = entry["parent_id"]
        copied["parent_id"] = event_ids[str(parent)] if parent is not None else None
        copied["content"] = [
            dict(part, id=f"{copied['id']}:block:{index}")
            for index, part in enumerate(entry["content"])
        ]
        events.append(copied)
    metadata = [
        {
            "name": name,
            "value": value,
            "origin": "imported",
            "producer": source.kind,
            "producer_version": source_version,
            "input_revision": "revision-input",
            "extensions": {},
        }
        for name, value in item.metadata
    ]
    doc: dict[str, object] = {
        "schema_version": 1,
        "id": conversation_id,
        "revision": "revision-pending",
        "source": {
            "kind": source.kind,
            "scope_id": source.scope_id,
            "native_id": item.native_id,
            "adapter_version": adapter_version,
            "source_version": source_version,
            "captured_at": captured_at.isoformat(),
            "snapshot_id": snapshot_id,
            "extensions": {},
        },
        "events": events,
        "artifacts": [],
        "relationships": list(item.relationships),
        "metadata": metadata,
        "coverage": item.coverage
        or {
            "messages": "available",
            "usage": "unknown",
            "prompts": "unknown",
            "tool_calls": "partial",
        },
        "extensions": {},
    }
    validate_conversation(doc)
    basis = json.loads(dump_conversation_json(doc))
    basis["source"]["captured_at"] = "1970-01-01T00:00:00+00:00"
    basis["source"]["snapshot_id"] = "revision-snapshot"
    revision = hashlib.sha256(canonical(basis)).hexdigest()
    doc["revision"] = revision
    validate_conversation(doc)
    return revision, doc


def _write_snapshot(
    settings: BenchwarmerSettings, source: Source, item: FileConversation
) -> tuple[str, str, bytes]:
    payload = canonical(item.native)
    digest = hashlib.sha256(payload).hexdigest()
    identity = hashlib.sha256(source.id.encode() + b"\0" + payload).hexdigest()
    snapshot_id = f"{source.kind}-snapshot-{identity[:32]}"
    kind_directory = settings.snapshots_dir / source.kind
    if kind_directory.is_symlink():
        raise FileConversationError("snapshot directory is unusable")
    directory = kind_directory / hashlib.sha256(source.id.encode()).hexdigest()[:32]
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    if directory.is_symlink():
        raise FileConversationError("snapshot directory is unusable")
    os.chmod(directory, 0o700)
    path = directory / f"{digest}.json"
    if path.exists():
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise FileConversationError("snapshot content conflicts")
    else:
        descriptor, name = tempfile.mkstemp(dir=directory, prefix=".snapshot-")
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.link(name, path)
        finally:
            os.unlink(name)
    return snapshot_id, path.relative_to(settings.data_root).as_posix(), payload


def import_file_conversations(
    settings: BenchwarmerSettings,
    session: Session,
    *,
    source_id: str,
    source_kind: str,
    batch_id: str,
    idempotency_key: str,
    items: tuple[FileConversation, ...],
    adapter_version: str,
    source_version: str | None = None,
    captured_at: dt.datetime | None = None,
) -> FileImportResult:
    """Publish a complete, explicit file observation; never infer deletions."""
    if session.in_transaction():
        raise FileConversationError("import requires an idle database session")
    if not items or len({item.native_id for item in items}) != len(items):
        raise FileConversationError("source identities are invalid")
    source = session.get(Source, source_id)
    if source is None or source.kind != source_kind:
        session.rollback()
        raise FileConversationError("configured source was not found")
    prior = session.scalar(
        select(ImportBatch).where(
            ImportBatch.source_id == source_id,
            ImportBatch.idempotency_key == idempotency_key,
        )
    )
    if prior is not None:
        session.rollback()
        return FileImportResult(prior.id, 0, 0, 0)
    state = session.get(SourceImportState, source_id)
    cursor_before = (
        ImportCursor.from_mapping(state.cursor) if state is not None else None
    )
    session.expunge(source)
    session.rollback()
    now = captured_at or utc_now()
    if now.tzinfo is None:
        raise FileConversationError("capture time must be timezone-aware")
    settings.initialize()
    prepared = [(*_write_snapshot(settings, source, item), item) for item in items]
    observed_versions = sorted({item.schema_version for item in items})
    state_schema_version = observed_versions[0] if len(observed_versions) == 1 else 0
    with session.begin():
        current = session.get(SourceImportState, source_id)
        observed = (
            ImportCursor.from_mapping(current.cursor) if current is not None else None
        )
        if observed != cursor_before:
            raise FileConversationError("source cursor changed; retry")
        cursor_after = ImportCursor(
            {"batch_id": batch_id, "source_schema_versions": observed_versions}
        )
        session.add(
            ImportBatch(
                id=batch_id,
                source_id=source_id,
                idempotency_key=idempotency_key,
                outcome="succeeded",
                cursor_before=cursor_before,
                cursor_after=cursor_after,
                observed_coverage=ImportCoverage(
                    {"messages": "available", "native_snapshots": "available"}
                ),
                started_at=now,
                completed_at=now,
            )
        )
        session.flush()
        revisions = snapshots = 0
        for snapshot_id, relative_path, payload, item in prepared:
            if session.get(NativeSnapshot, snapshot_id) is None:
                session.add(
                    NativeSnapshot(
                        id=snapshot_id,
                        source_id=source_id,
                        import_batch_id=batch_id,
                        content_sha256=hashlib.sha256(payload).hexdigest(),
                        relative_path=relative_path,
                        byte_length=len(payload),
                        captured_at=now,
                        created_at=now,
                    )
                )
                snapshots += 1
            native_session = session.get(
                NativeSession, {"source_id": source_id, "native_id": item.native_id}
            )
            if native_session is None:
                session.add(
                    NativeSession(
                        source_id=source_id,
                        native_id=item.native_id,
                        parent_native_id=None,
                        source_version=item.source_version or source_version,
                        schema_version=item.schema_version,
                        application_version=None,
                        payload={"native_id": item.native_id},
                        snapshot_id=snapshot_id,
                        source_present=True,
                        first_seen_at=now,
                        last_seen_at=now,
                    )
                )
            else:
                if native_session.schema_version != item.schema_version:
                    raise FileConversationError("source-native identity changed schema")
                native_session.snapshot_id = snapshot_id
                native_session.last_seen_at = now
                native_session.source_present = True
            session.add(
                SourcePresence(
                    source_id=source_id,
                    batch_id=batch_id,
                    subject_kind="session",
                    native_id=item.native_id,
                    present=True,
                    observed_at=now,
                )
            )
            session.flush()
            for ordinal, entry in enumerate(item.events, start=1):
                entry_id = str(entry["native_id"])
                native_message_id = hashlib.sha256(
                    f"{item.native_id}\0{entry_id}".encode()
                ).hexdigest()
                stored = session.get(
                    NativeMessage,
                    {"source_id": source_id, "native_id": native_message_id},
                )
                content = (
                    "\n".join(
                        str(part["text"])
                        for part in entry["content"]
                        if part["kind"] == "text" and isinstance(part["text"], str)
                    )
                    or None
                )
                timestamp = entry.get("occurred_at")
                try:
                    epoch = (
                        dt.datetime.fromisoformat(str(timestamp)).timestamp()
                        if timestamp is not None
                        else 0.0
                    )
                except ValueError:
                    epoch = 0.0
                values = {
                    "native_order": ordinal,
                    "session_native_id": item.native_id,
                    "role": str(entry["role"]),
                    "content": content,
                    "tool_call_id": None,
                    "tool_name": None,
                    "reasoning": None,
                    "source_timestamp": epoch,
                    "payload": entry,
                    "snapshot_id": snapshot_id,
                    "source_present": True,
                    "last_seen_at": now,
                }
                if stored is None:
                    session.add(
                        NativeMessage(
                            source_id=source_id,
                            native_id=native_message_id,
                            first_seen_at=now,
                            **values,
                        )
                    )
                else:
                    for key, value in values.items():
                        setattr(stored, key, value)
                session.add(
                    SourcePresence(
                        source_id=source_id,
                        batch_id=batch_id,
                        subject_kind="message",
                        native_id=native_message_id,
                        present=True,
                        observed_at=now,
                    )
                )
            revision, doc = document_for(
                source, item, snapshot_id, now, adapter_version, source_version
            )
            existing = session.scalar(
                select(ConversationRevision).where(
                    ConversationRevision.source_id == source_id,
                    ConversationRevision.native_id == item.native_id,
                    ConversationRevision.revision == revision,
                )
            )
            if existing is None:
                session.add(
                    ConversationRevision(
                        id=f"{doc['id']}-{revision[:16]}",
                        source_id=source_id,
                        native_id=item.native_id,
                        revision=revision,
                        snapshot_id=snapshot_id,
                        document=doc,
                        captured_at=now,
                        created_at=now,
                    )
                )
                revisions += 1
        if current is None:
            session.add(
                SourceImportState(
                    source_id=source_id,
                    adapter_version=adapter_version,
                    schema_version=state_schema_version,
                    cursor=cursor_after.to_storage(),
                    updated_at=now,
                )
            )
        else:
            current.adapter_version = adapter_version
            current.schema_version = state_schema_version
            current.cursor = cursor_after.to_storage()
            current.updated_at = now
    return FileImportResult(batch_id, len(items), revisions, snapshots)
