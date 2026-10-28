"""One place where import kinds, export sinks, and scrub detectors are named.

Registration is internal: this module lists the built-ins, and a new adapter
is added by appending to the tuples below (or by calling the ``register_*``
functions from application code before the first lookup). There are no entry
points and nothing is discovered from the environment, so the set of kinds the
API advertises is exactly what this file says.

- An **importer** turns files at a host path into library conversations
  through ``benchwarmer.adapters.file_conversations.import_file_conversations``.
- An **export sink** renders an approved task version's case record somewhere.
  The ``file`` sink is the one the web download and the pull route use.
- A **scrub detector** is one built-in category of ``benchwarmer.anonymize``;
  the registry wraps them by kind without changing how the scrubber runs them.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Literal, Protocol

from sqlalchemy.orm import Session

from benchwarmer.adapters.chatgpt.reader import import_chatgpt_export
from benchwarmer.adapters.conversation_file.reader import import_conversation_path
from benchwarmer.adapters.file_conversations import FileImportResult
from benchwarmer.adapters.pi.reader import import_pi_path
from benchwarmer.anonymize import BUILTIN_DETECTORS, ScrubCategory, ScrubDetector
from benchwarmer.config import BenchwarmerSettings
from benchwarmer.interchange.format import SOURCE_KIND as CONVERSATION_FILE_KIND
from benchwarmer.services.case_export import CaseRecord


class UnknownKind(KeyError):
    """No registration has the requested kind or name."""


class PathImporter(Protocol):
    def __call__(
        self,
        settings: BenchwarmerSettings,
        session: Session,
        *,
        source_id: str,
        path: Path,
        batch_id: str,
        idempotency_key: str,
    ) -> FileImportResult: ...


Accepts = Literal["file", "directory", "file_or_directory"]


@dataclass(frozen=True, slots=True)
class ImporterSpec:
    """A source kind whose files can be imported from a path on this host."""

    kind: str
    label: str
    accepts: Accepts
    description: str
    import_path: PathImporter


@dataclass(frozen=True, slots=True)
class ExportSink:
    """Where a case record can go. ``render`` is deterministic for a record."""

    name: str
    description: str
    media_type: str
    filename: Callable[[CaseRecord], str]
    render: Callable[[CaseRecord], bytes]

    def write(self, record: CaseRecord, directory: Path) -> Path:
        """Write the rendered record under ``directory`` and return its path."""
        if not directory.is_dir():
            raise FileNotFoundError(f"{directory} is not a directory")
        target = directory / self.filename(record)
        target.write_bytes(self.render(record))
        return target


def _case_filename(record: CaseRecord) -> str:
    return f"case-{record.case['id']}-v{record.case['version']}.json"


def _case_json(record: CaseRecord) -> bytes:
    text = json.dumps(
        record.model_dump(mode="json"), indent=2, sort_keys=True, ensure_ascii=False
    )
    return (text + "\n").encode("utf-8")


_IMPORTERS: dict[str, ImporterSpec] = {}
_SINKS: dict[str, ExportSink] = {}


def register_importer(spec: ImporterSpec) -> ImporterSpec:
    if spec.kind in _IMPORTERS:
        raise ValueError(f"importer kind {spec.kind!r} is already registered")
    _IMPORTERS[spec.kind] = spec
    return spec


def register_export_sink(sink: ExportSink) -> ExportSink:
    if sink.name in _SINKS:
        raise ValueError(f"export sink {sink.name!r} is already registered")
    _SINKS[sink.name] = sink
    return sink


def importers() -> tuple[ImporterSpec, ...]:
    return tuple(_IMPORTERS.values())


def importer_kinds() -> tuple[str, ...]:
    """Source kinds that accept a host path, in registration order."""
    return tuple(_IMPORTERS)


def importer(kind: str) -> ImporterSpec:
    try:
        return _IMPORTERS[kind]
    except KeyError:
        raise UnknownKind(kind) from None


def export_sinks() -> tuple[ExportSink, ...]:
    return tuple(_SINKS.values())


def export_sink(name: str) -> ExportSink:
    try:
        return _SINKS[name]
    except KeyError:
        raise UnknownKind(name) from None


def scrub_detectors() -> tuple[ScrubDetector, ...]:
    """The built-in detectors in the order the scrubber applies them."""
    return BUILTIN_DETECTORS


def scrub_detector_kinds() -> tuple[ScrubCategory, ...]:
    seen: list[ScrubCategory] = []
    for detector in BUILTIN_DETECTORS:
        if detector.kind not in seen:
            seen.append(detector.kind)
    return tuple(seen)


def scrub_detectors_for(kind: str) -> tuple[ScrubDetector, ...]:
    found = tuple(d for d in BUILTIN_DETECTORS if d.kind == kind)
    if not found:
        raise UnknownKind(kind)
    return found


# Built-in registrations. Order is the order the API lists kinds in.
register_importer(
    ImporterSpec(
        kind="pi",
        label="Pi sessions",
        accepts="file_or_directory",
        description="A Pi session JSONL file or a directory of sessions.",
        import_path=import_pi_path,
    )
)
register_importer(
    ImporterSpec(
        kind="chatgpt",
        label="ChatGPT account export",
        accepts="file",
        description="A conversations.json or the export zip that contains it.",
        import_path=import_chatgpt_export,
    )
)
register_importer(
    ImporterSpec(
        kind=CONVERSATION_FILE_KIND,
        label="Conversation files",
        accepts="file_or_directory",
        description=(
            "A Benchwarmer conversation file (format v1) or a directory of them; "
            "see docs/conversation-interchange.md."
        ),
        import_path=import_conversation_path,
    )
)
register_export_sink(
    ExportSink(
        name="file",
        description="The case record as one indented JSON file.",
        media_type="application/json",
        filename=_case_filename,
        render=_case_json,
    )
)

__all__ = [
    "Accepts",
    "ExportSink",
    "ImporterSpec",
    "PathImporter",
    "UnknownKind",
    "export_sink",
    "export_sinks",
    "importer",
    "importer_kinds",
    "importers",
    "register_export_sink",
    "register_importer",
    "scrub_detector_kinds",
    "scrub_detectors",
    "scrub_detectors_for",
]
