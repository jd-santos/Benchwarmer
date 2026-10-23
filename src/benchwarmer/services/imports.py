"""Import conversation files from this host's configured import roots.

Imports never start model work. A path is accepted only when it resolves to a
real file or directory under one of ``settings.import_roots``; the roots are the
operator's explicit configuration of where source files may be read from.
"""

from __future__ import annotations

from dataclasses import dataclass
import datetime as dt
import hashlib
from pathlib import Path
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from benchwarmer.adapters.chatgpt.reader import import_chatgpt_export
from benchwarmer.adapters.file_conversations import (
    FileConversationError,
    FileImportResult,
)
from benchwarmer.adapters.pi.reader import import_pi_directory, import_pi_session
from benchwarmer.config import BenchwarmerSettings
from benchwarmer.models.import_batch import ImportBatch
from benchwarmer.models.source import Source

# Source kinds whose files can be imported from a path on this host.
IMPORTABLE_KINDS: tuple[str, ...] = ("pi", "chatgpt")

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
    if source.kind not in IMPORTABLE_KINDS:
        raise ImportRequestError(
            f"{source.kind} sources are collected, not imported from a path"
        )
    path = resolve_import_path(settings, raw_path)
    kind = source.kind
    session.expunge(source)
    session.rollback()

    started = now or dt.datetime.now(dt.UTC)
    batch_id = f"{kind}-ui-{started.strftime('%Y%m%dT%H%M%S%fZ')}"
    idempotency_key = _content_key(path)
    try:
        if kind == "pi":
            importer = import_pi_directory if path.is_dir() else import_pi_session
        else:
            importer = import_chatgpt_export
        result: FileImportResult = importer(
            settings,
            session,
            source_id=source_id,
            path=path,
            batch_id=batch_id,
            idempotency_key=idempotency_key,
        )
    except FileConversationError as error:
        # The importer wrote nothing; record the failed attempt so the history shows it.
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
