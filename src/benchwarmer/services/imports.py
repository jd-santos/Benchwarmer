"""Import conversation files from this host's configured import roots.

Imports never start model work. A path is accepted only when it resolves to a
real file or directory under one of ``settings.import_roots``; the roots are the
operator's explicit configuration of where source files may be read from.
"""

from __future__ import annotations

from dataclasses import dataclass
import datetime as dt
import hashlib
import os
from pathlib import Path
import tempfile
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from benchwarmer import registry
from benchwarmer.adapters.conversation_file.reader import (
    conversation_from_document,
    import_conversation_items,
)
from benchwarmer.adapters.file_conversations import (
    FileConversationError,
    FileImportResult,
    canonical,
    conversation_id_for,
)
from benchwarmer.config import BenchwarmerSettings
from benchwarmer.interchange.format import SOURCE_KIND as CONVERSATION_FILE_KIND
from benchwarmer.models import ConversationRevision
from benchwarmer.models.import_batch import ImportBatch
from benchwarmer.models.source import Source

ImportOutcome = Literal["succeeded", "failed", "unchanged"]


class ImportRequestError(ValueError):
    """The import request named an unusable source or path."""


class SourceNotFound(LookupError):
    """No configured source has the requested id."""


@dataclass(frozen=True)
class ImportBatchSummary:
    id: str
    source_id: str
    outcome: str
    started_at: dt.datetime
    completed_at: dt.datetime
    error_summary: str | None


@dataclass(frozen=True)
class ImportRun:
    """What one requested import did."""

    batch_id: str
    outcome: ImportOutcome
    conversations: int
    revisions: int
    snapshots: int
    error_summary: str | None


@dataclass(frozen=True)
class ConversationFileImport:
    """Where one uploaded conversation file landed."""

    batch_id: str
    outcome: ImportOutcome
    source_id: str
    native_id: str
    conversation_id: str
    revision: str | None
    new_revision: bool
    staged_path: str


def resolve_import_path(settings: BenchwarmerSettings, raw_path: str) -> Path:
    """Resolve a requested path and require it to sit under a configured import root."""
    if not raw_path.strip():
        raise ImportRequestError("path must not be empty")
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        raise ImportRequestError("path must be absolute")
    if not settings.import_roots:
        raise ImportRequestError(
            "no import roots are configured; set BENCHWARMER_IMPORT_ROOTS on the server"
        )
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as error:
        raise ImportRequestError("path does not exist") from error
    for root in settings.import_roots:
        try:
            resolved.relative_to(root.resolve())
        except ValueError:
            continue
        return resolved
    raise ImportRequestError("path is outside the configured import roots")


def list_import_batches(
    session: Session, source_id: str
) -> tuple[ImportBatchSummary, ...]:
    """Import attempts for one source, most recent first."""
    if session.get(Source, source_id) is None:
        raise SourceNotFound(source_id)
    rows = session.scalars(
        select(ImportBatch)
        .where(ImportBatch.source_id == source_id)
        .order_by(ImportBatch.started_at.desc(), ImportBatch.id)
    )
    return tuple(
        ImportBatchSummary(
            id=row.id,
            source_id=row.source_id,
            outcome=row.outcome,
            started_at=row.started_at,
            completed_at=row.completed_at,
            error_summary=row.error_summary,
        )
        for row in rows
    )


def _content_key(path: Path) -> str:
    """A key that repeats only while the files under ``path`` are unchanged."""
    digest = hashlib.sha256()
    files = sorted(path.rglob("*")) if path.is_dir() else [path]
    for file in files:
        if not file.is_file():
            continue
        stat = file.stat()
        digest.update(
            f"{file.relative_to(path.parent).as_posix()}\0{stat.st_size}\0{stat.st_mtime_ns}\n".encode()
        )
    return digest.hexdigest()


def run_file_import(
    settings: BenchwarmerSettings,
    session: Session,
    *,
    source_id: str,
    raw_path: str,
    now: dt.datetime | None = None,
) -> ImportRun:
    """Import the files at ``raw_path`` into ``source_id`` and record the attempt."""
    source = session.get(Source, source_id)
    if source is None:
        raise SourceNotFound(source_id)
    try:
        spec = registry.importer(source.kind)
    except registry.UnknownKind:
        raise ImportRequestError(
            f"{source.kind} sources are collected, not imported from a path"
        ) from None
    path = resolve_import_path(settings, raw_path)
    kind = source.kind
    session.expunge(source)
    session.rollback()
    if path.is_dir() and spec.accepts == "file":
        raise ImportRequestError(
            f"{kind} sources import a single file, not a directory"
        )
    if path.is_file() and spec.accepts == "directory":
        raise ImportRequestError(f"{kind} sources import a directory, not a file")

    started = now or dt.datetime.now(dt.UTC)
    batch_id = f"{kind}-ui-{started.strftime('%Y%m%dT%H%M%S%fZ')}"
    idempotency_key = _content_key(path)
    try:
        result: FileImportResult = spec.import_path(
            settings,
            session,
            source_id=source_id,
            path=path,
            batch_id=batch_id,
            idempotency_key=idempotency_key,
        )
    except FileConversationError as error:
        _record_failure(session, source_id, batch_id, idempotency_key, started, error)
        return ImportRun(batch_id, "failed", 0, 0, 0, str(error) or "import failed")

    if result.batch_id != batch_id:
        # An earlier batch already imported exactly these files.
        return ImportRun(result.batch_id, "unchanged", 0, 0, 0, None)
    return ImportRun(
        result.batch_id,
        "succeeded",
        result.conversations,
        result.revisions,
        result.snapshots,
        None,
    )


def _record_failure(
    session: Session,
    source_id: str,
    batch_id: str,
    idempotency_key: str,
    started: dt.datetime,
    error: Exception,
) -> None:
    """The importer wrote nothing; record the failed attempt so the history shows it."""
    session.rollback()
    completed = dt.datetime.now(dt.UTC)
    with session.begin():
        session.add(
            ImportBatch(
                id=batch_id,
                source_id=source_id,
                idempotency_key=f"{idempotency_key}:{batch_id}",
                outcome="failed",
                started_at=started,
                completed_at=max(completed, started),
                error_summary=str(error) or "import failed",
            )
        )


def conversation_file_source_id(scope_id: str) -> str:
    """The source id Benchwarmer assigns to one conversation-file scope."""
    return (
        "conversation-file-" + hashlib.sha256(scope_id.encode("utf-8")).hexdigest()[:24]
    )


def _ensure_conversation_file_source(session: Session, scope_id: str) -> str:
    """Find or create the ``conversation_file`` source for one writer scope."""
    source_id = conversation_file_source_id(scope_id)
    with session.begin():
        existing = session.scalar(
            select(Source).where(
                Source.kind == CONVERSATION_FILE_KIND, Source.scope_id == scope_id
            )
        )
        if existing is not None:
            return existing.id
        session.add(
            Source(
                id=source_id,
                kind=CONVERSATION_FILE_KIND,
                scope_id=scope_id,
                display_name=f"Conversation files: {scope_id}"[:255],
            )
        )
    return source_id


def _stage_conversation_file(
    settings: BenchwarmerSettings, payload: bytes, digest: str
) -> Path:
    """Keep the received bytes under the data root before anything is imported."""
    settings.initialize()
    directory = settings.import_staging_dir / CONVERSATION_FILE_KIND
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    if directory.is_symlink():
        raise FileConversationError("staging directory is unusable")
    target = directory / f"{digest}.json"
    if target.exists():
        if target.is_symlink():
            raise FileConversationError("staging path is unusable")
        return target
    descriptor, name = tempfile.mkstemp(dir=directory, prefix=".upload-")
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(name, 0o600)
        os.link(name, target)
    except FileExistsError:
        pass
    finally:
        os.unlink(name)
    return target


def import_conversation_file_document(
    settings: BenchwarmerSettings,
    session: Session,
    *,
    document: dict[str, Any],
    source_id: str | None = None,
    now: dt.datetime | None = None,
) -> ConversationFileImport:
    """Import one conversation file received as a request body.

    The file is validated, staged under the data root, and imported through
    the same path as host files. Without ``source_id`` the file's ``scope_id``
    selects (or creates) the ``conversation_file`` source for that scope. The
    same bytes import once; a changed file yields a new revision.
    """
    try:
        item = conversation_from_document(document)
    except FileConversationError as error:
        raise ImportRequestError(str(error)) from None
    scope_id = str(document["scope_id"])
    if source_id is None:
        source_id = _ensure_conversation_file_source(session, scope_id)
    else:
        source = session.get(Source, source_id)
        if source is None:
            session.rollback()
            raise SourceNotFound(source_id)
        kind, source_scope = source.kind, source.scope_id
        session.rollback()
        if kind != CONVERSATION_FILE_KIND:
            raise ImportRequestError(
                f"source {source_id} is not a conversation_file source"
            )
        if source_scope != scope_id:
            raise ImportRequestError(
                "conversation file scope_id does not match the source"
            )

    payload = canonical(document)
    digest = hashlib.sha256(payload).hexdigest()
    staged = _stage_conversation_file(settings, payload, digest)
    started = now or dt.datetime.now(dt.UTC)
    batch_id = f"{CONVERSATION_FILE_KIND}-api-{started.strftime('%Y%m%dT%H%M%S%fZ')}"
    conversation_id = conversation_id_for(source_id, item.native_id)
    try:
        result = import_conversation_items(
            settings,
            session,
            source_id=source_id,
            items=(item,),
            batch_id=batch_id,
            idempotency_key=f"sha256:{digest}",
        )
    except FileConversationError as error:
        _record_failure(
            session, source_id, batch_id, f"sha256:{digest}", started, error
        )
        return ConversationFileImport(
            batch_id,
            "failed",
            source_id,
            item.native_id,
            conversation_id,
            None,
            False,
            str(staged.relative_to(settings.data_root)),
        )
    if result.batch_id != batch_id:
        # These exact bytes were imported before; report where they live.
        revision = session.scalar(
            select(ConversationRevision.revision)
            .where(
                ConversationRevision.source_id == source_id,
                ConversationRevision.native_id == item.native_id,
            )
            .order_by(ConversationRevision.created_at.desc())
            .limit(1)
        )
        session.rollback()
        return ConversationFileImport(
            result.batch_id,
            "unchanged",
            source_id,
            item.native_id,
            conversation_id,
            revision,
            False,
            str(staged.relative_to(settings.data_root)),
        )
    imported = result.items[0]
    return ConversationFileImport(
        batch_id,
        "succeeded",
        source_id,
        item.native_id,
        imported.conversation_id,
        imported.revision,
        imported.new_revision,
        str(staged.relative_to(settings.data_root)),
    )
