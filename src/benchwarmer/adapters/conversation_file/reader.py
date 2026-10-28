"""Read conversation files from disk or a request and persist them privately.

A conversation file is Benchwarmer's own interchange format, so there is no
source-specific parsing here: the file is validated, converted with
``benchwarmer.interchange``, and handed to the shared persistence path. The
whole file is the retained native snapshot.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from benchwarmer.adapters.file_conversations import (
    FileConversation,
    FileConversationError,
    FileImportResult,
    import_file_conversations,
)
from benchwarmer.config import BenchwarmerSettings
from benchwarmer.interchange.format import (
    ADAPTER_VERSION,
    SOURCE_KIND,
    ConversationFileError,
    parse_conversation_file,
    to_file_conversation,
    validate_conversation_file,
)
from benchwarmer.models.source import Source

MAX_FILE_BYTES = 64 * 1024 * 1024


def _invalid(error: ConversationFileError) -> FileConversationError:
    return FileConversationError(str(error))


def conversation_from_document(document: dict[str, Any]) -> FileConversation:
    """Validate one parsed conversation file and convert it for import."""
    issues = validate_conversation_file(document)
    if issues:
        raise _invalid(ConversationFileError(issues))
    return to_file_conversation(document)


def read_conversation_file(path: Path) -> FileConversation:
    """Read one conversation file; symlinks, oversized, and invalid files fail closed."""
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise FileConversationError("conversation file path is unusable")
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            raise FileConversationError("conversation file is too large")
        raw = path.read_bytes()
    except OSError as error:
        raise FileConversationError("conversation file could not be read") from error
    try:
        document = parse_conversation_file(raw)
    except ConversationFileError as error:
        raise _invalid(error) from None
    return conversation_from_document(document)


def read_conversation_files(path: Path) -> tuple[FileConversation, ...]:
    """Read every ``*.json`` conversation file below one directory."""
    if not path.is_absolute() or path.is_symlink() or not path.is_dir():
        raise FileConversationError("conversation file directory is unusable")
    files = sorted(file for file in path.rglob("*.json") if not file.is_symlink())
    if not files:
        raise FileConversationError("directory contains no conversation files")
    items = tuple(read_conversation_file(file) for file in files)
    if len({item.native_id for item in items}) != len(items):
        raise FileConversationError("conversation files repeat a native_id")
    return items


def _scope_id(item: FileConversation) -> str:
    return str(item.native["scope_id"])


def _check_scope(
    session: Session, source_id: str, items: tuple[FileConversation, ...]
) -> None:
    """Every file must name the configured source's scope; nothing is merged across scopes."""
    if session.in_transaction():
        raise FileConversationError("import requires an idle database session")
    source = session.get(Source, source_id)
    scope = source.scope_id if source is not None else None
    session.rollback()
    if source is None:
        raise FileConversationError("configured source was not found")
    if any(_scope_id(item) != scope for item in items):
        raise FileConversationError(
            "conversation file scope_id does not match the source"
        )


def import_conversation_items(
    settings: BenchwarmerSettings,
    session: Session,
    *,
    source_id: str,
    items: tuple[FileConversation, ...],
    batch_id: str,
    idempotency_key: str,
) -> FileImportResult:
    """Persist already-converted conversation files into one source."""
    _check_scope(session, source_id, items)
    return import_file_conversations(
        settings,
        session,
        source_id=source_id,
        source_kind=SOURCE_KIND,
        batch_id=batch_id,
        idempotency_key=idempotency_key,
        items=items,
        adapter_version=ADAPTER_VERSION,
        source_version=None,
    )


def import_conversation_path(
    settings: BenchwarmerSettings,
    session: Session,
    *,
    source_id: str,
    path: Path,
    batch_id: str,
    idempotency_key: str,
) -> FileImportResult:
    """Import one conversation file or a directory of them from a host path."""
    items = (
        read_conversation_files(path)
        if path.is_dir()
        else (read_conversation_file(path),)
    )
    return import_conversation_items(
        settings,
        session,
        source_id=source_id,
        items=items,
        batch_id=batch_id,
        idempotency_key=idempotency_key,
    )
