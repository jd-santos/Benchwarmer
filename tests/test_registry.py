"""The registry names every import kind, export sink, and scrub detector."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from benchwarmer import registry
from benchwarmer.anonymize import _PRIORITY, Scrubber
from benchwarmer.services.case_export import CaseRecord


def test_importers_cover_the_file_source_kinds() -> None:
    assert registry.importer_kinds() == ("pi", "chatgpt", "conversation_file")
    spec = registry.importer("conversation_file")
    assert spec.accepts == "file_or_directory"
    assert registry.importer("chatgpt").accepts == "file"
    with pytest.raises(registry.UnknownKind):
        registry.importer("hermes")
    with pytest.raises(ValueError, match="already registered"):
        registry.register_importer(spec)


def test_file_sink_writes_the_case_record(tmp_path: Path) -> None:
    record = CaseRecord(
        case={"id": "task-1", "version": 2}, candidate={}, judge={}, digest="d" * 64
    )
    [sink] = registry.export_sinks()
    assert sink is registry.export_sink("file")
    assert sink.filename(record) == "case-task-1-v2.json"
    written = sink.write(record, tmp_path)
    assert written == tmp_path / "case-task-1-v2.json"
    assert json.loads(written.read_text()) == record.model_dump(mode="json")
    assert sink.render(record) == sink.render(record)
    with pytest.raises(FileNotFoundError):
        sink.write(record, tmp_path / "missing")
    with pytest.raises(registry.UnknownKind):
        registry.export_sink("bucket")


def test_scrub_detectors_wrap_the_built_in_categories() -> None:
    kinds = registry.scrub_detector_kinds()
    assert kinds == (
        "term",
        "email",
        "url",
        "path",
        "ipv6",
        "ipv4",
        "secret",
        "hostname",
    )
    assert list(kinds) == sorted(kinds, key=_PRIORITY.__getitem__)
    assert len(registry.scrub_detectors_for("secret")) == 3
    with pytest.raises(registry.UnknownKind):
        registry.scrub_detectors_for("phone")
    # The scrubber still runs exactly these detectors.
    scrubber = Scrubber(["Alpha"])
    text = scrubber.scrub_text(
        "Alpha wrote to someone@example.com from 10.0.0.1", event_id=None, block_id=None
    )
    assert text == "<term-1> wrote to <email-1> from <ipv4-1>"
    assert set(scrubber.counts) <= set(kinds)
