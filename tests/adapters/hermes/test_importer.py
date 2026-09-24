"""Synthetic acceptance tests for incremental Hermes persistence."""

from __future__ import annotations

from dataclasses import replace
import datetime as dt
import json
from pathlib import Path
import sqlite3
import stat
from types import MappingProxyType

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from benchwarmer.adapters.hermes.importer import (
    HermesImportError,
    HermesImportRequest,
    import_hermes,
)
from benchwarmer.adapters.hermes.reader import HermesReadRequest, read_hermes_snapshot
from benchwarmer.config import BenchwarmerSettings
from benchwarmer.conversations import validate_conversation
from benchwarmer.models import (
    Base,
    ConversationRevision,
    ImportBatch,
    NativeMessage,
    NativeSession,
    NativeSnapshot,
    NativeUsage,
    Source,
    SourceImportState,
)

FIXTURE_DIRECTORY = Path(__file__).parents[2] / "fixtures" / "hermes" / "schema-30"
SCHEMA = (FIXTURE_DIRECTORY / "schema.sql").read_text()


def _source_database(path: Path) -> Path:
    connection = sqlite3.connect(path)
    try:
        connection.executescript(SCHEMA)
        connection.execute("PRAGMA journal_mode = WAL")
        connection.commit()
    finally:
        connection.close()
    return path


def _count(session: Session, model: type[object]) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


def _request(
    source_path: Path,
    batch_id: str,
    idempotency_key: str,
    captured_at: dt.datetime,
    *,
    source_id: str = "source-hermes",
) -> HermesImportRequest:
    return HermesImportRequest(
        source_id=source_id,
        batch_id=batch_id,
        idempotency_key=idempotency_key,
        read_request=HermesReadRequest(source_path, "fixture-app-1.0"),
        captured_at=captured_at,
    )


def _context(tmp_path: Path) -> tuple[Path, BenchwarmerSettings, Session, Engine]:
    source_path = _source_database(tmp_path / "state.db")
    settings = BenchwarmerSettings(data_root=tmp_path / "private")
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'benchwarmer.sqlite3'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    session = factory()
    session.add(
        Source(
            id="source-hermes",
            kind="hermes",
            scope_id="fixture-profile",
            display_name="Synthetic Hermes",
        )
    )
    session.commit()
    return source_path, settings, session, engine


def test_initial_import_persists_native_snapshot_and_normalized_revisions(
    tmp_path: Path,
) -> None:
    source_path, settings, session, engine = _context(tmp_path)
    try:
        result = import_hermes(
            settings,
            session,
            _request(
                source_path,
                "batch-initial",
                "attempt-initial",
                dt.datetime(2026, 9, 19, 12, 0, tzinfo=dt.UTC),
            ),
        )

        assert result.outcome == "succeeded"
        assert result.sessions == 2
        assert result.messages == 2
        assert result.usages == 1
        assert result.revisions == 2
        assert _count(session, NativeSession) == 2
        assert _count(session, NativeMessage) == 2
        assert _count(session, NativeUsage) == 1
        assert _count(session, NativeSnapshot) == 1
        assert _count(session, ConversationRevision) == 2
        assert _count(session, SourceImportState) == 1

        usage = session.scalar(select(NativeUsage))
        assert usage is not None
        assert usage.task == ""
        assert usage.payload["actual_cost_usd"] == 0

        revisions = session.scalars(select(ConversationRevision)).all()
        for revision in revisions:
            validate_conversation(revision.document)
            assert revision.document["source"]["snapshot_id"] == result.snapshot_id

        snapshot = session.scalar(select(NativeSnapshot))
        assert snapshot is not None
        snapshot_path = settings.data_root / snapshot.relative_path
        assert snapshot_path.is_file()
        assert stat.S_IMODE(snapshot_path.stat().st_mode) == 0o600
        assert (
            json.loads(snapshot_path.read_text())["tables"]["sessions"][0][
                "fixture_extension"
            ]
            == "extra"
        )
    finally:
        session.close()
        engine.dispose()


def test_identical_content_from_two_sources_gets_distinct_snapshot_identity(
    tmp_path: Path,
) -> None:
    source_path, settings, session, engine = _context(tmp_path)
    try:
        session.add(
            Source(
                id="source-hermes-two",
                kind="hermes",
                scope_id="fixture-profile-two",
                display_name="Synthetic Hermes Two",
            )
        )
        session.commit()
        first = import_hermes(
            settings,
            session,
            _request(
                source_path,
                "batch-one",
                "attempt-one",
                dt.datetime(2026, 9, 19, 12, 0, tzinfo=dt.UTC),
            ),
        )
        second = import_hermes(
            settings,
            session,
            _request(
                source_path,
                "batch-two",
                "attempt-two",
                dt.datetime(2026, 9, 19, 12, 1, tzinfo=dt.UTC),
                source_id="source-hermes-two",
            ),
        )

        assert first.outcome == second.outcome == "succeeded"
        assert first.snapshot_id != second.snapshot_id
        assert _count(session, NativeSnapshot) == 2
    finally:
        session.close()
        engine.dispose()


def test_unchanged_import_is_idempotent_and_reuses_revision_and_snapshot(
    tmp_path: Path,
) -> None:
    source_path, settings, session, engine = _context(tmp_path)
    try:
        first = import_hermes(
            settings,
            session,
            _request(
                source_path,
                "batch-one",
                "attempt-one",
                dt.datetime(2026, 9, 19, 12, 0, tzinfo=dt.UTC),
            ),
        )
        second = import_hermes(
            settings,
            session,
            _request(
                source_path,
                "batch-two",
                "attempt-two",
                dt.datetime(2026, 9, 19, 12, 1, tzinfo=dt.UTC),
            ),
        )
        duplicate = import_hermes(
            settings,
            session,
            _request(
                source_path,
                "batch-duplicate-id",
                "attempt-two",
                dt.datetime(2026, 9, 19, 12, 2, tzinfo=dt.UTC),
            ),
        )

        assert first.outcome == second.outcome == duplicate.outcome == "succeeded"
        assert second.messages == 0
        assert second.revisions == 0
        assert duplicate.batch_id == "batch-two"
        assert duplicate.snapshot_id == second.snapshot_id == first.snapshot_id
        assert _count(session, NativeSnapshot) == 1
        assert _count(session, ConversationRevision) == 2
        assert _count(session, ImportBatch) == 2
        state = session.get(SourceImportState, "source-hermes")
        assert state is not None
        assert state.cursor == {
            "schema_version": 1,
            "value": {
                "last_message_id": 2,
                "snapshot_id": first.snapshot_id,
                "source_schema_version": 30,
            },
        }
    finally:
        session.close()
        engine.dispose()


def test_appended_message_and_mutable_usage_update_only_new_message_and_revision(
    tmp_path: Path,
) -> None:
    source_path, settings, session, engine = _context(tmp_path)
    try:
        first = import_hermes(
            settings,
            session,
            _request(
                source_path,
                "batch-one",
                "attempt-one",
                dt.datetime(2026, 9, 19, 12, 0, tzinfo=dt.UTC),
            ),
        )
        connection = sqlite3.connect(source_path)
        try:
            connection.execute(
                "UPDATE messages SET content = 'edited second', "
                'tool_calls = \'[{"id":"call-1","name":"lookup"}]\' '
                "WHERE id = 2"
            )
            connection.execute(
                "INSERT INTO messages "
                "(id, session_id, role, content, tool_call_id, timestamp) "
                "VALUES (3, 'session-a', 'tool', 'tool result', 'call-1', 3)"
            )
            connection.execute(
                "UPDATE session_model_usage SET input_tokens = 16, output_tokens = 7"
            )
            connection.commit()
        finally:
            connection.close()

        second = import_hermes(
            settings,
            session,
            _request(
                source_path,
                "batch-two",
                "attempt-two",
                dt.datetime(2026, 9, 19, 12, 1, tzinfo=dt.UTC),
            ),
        )

        assert second.outcome == "succeeded"
        assert second.messages == 1
        assert second.usages == 1
        assert second.revisions == 1
        assert _count(session, NativeMessage) == 3
        assert _count(session, ConversationRevision) == 3
        usage = session.scalar(select(NativeUsage))
        assert usage is not None
        assert usage.payload["input_tokens"] == 16
        assert usage.payload["output_tokens"] == 7
        edited = session.get(
            NativeMessage, {"source_id": "source-hermes", "native_id": "2"}
        )
        assert edited is not None
        assert edited.content == "edited second"
        revision = session.scalar(
            select(ConversationRevision)
            .where(ConversationRevision.native_id == "session-a")
            .order_by(ConversationRevision.created_at.desc())
        )
        assert revision is not None
        assert revision.document["events"][1]["content"][1]["tool_call_id"] == "call-1"
        assert revision.document["events"][2]["content"][1]["kind"] == "tool_result"
        assert first.cursor_after != second.cursor_after
    finally:
        session.close()
        engine.dispose()


def test_failed_persistence_records_failure_without_advancing_cursor(
    tmp_path: Path,
) -> None:
    source_path, settings, session, engine = _context(tmp_path)
    try:
        valid = read_hermes_snapshot(HermesReadRequest(source_path, "fixture-app-1.0"))
        tables = dict(valid.tables)
        bad_usage = dict(tables["session_model_usage"][0])
        bad_usage["task"] = []
        tables["session_model_usage"] = (MappingProxyType(bad_usage),)
        invalid = replace(valid, tables=MappingProxyType(tables))

        result = import_hermes(
            settings,
            session,
            _request(
                source_path,
                "batch-failed",
                "attempt-failed",
                dt.datetime(2026, 9, 19, 12, 0, tzinfo=dt.UTC),
            ),
            reader=lambda _: invalid,
        )

        assert result.outcome == "failed"
        assert result.error_summary == "Hermes import failed"
        assert _count(session, NativeSession) == 0
        assert _count(session, NativeMessage) == 0
        assert _count(session, NativeSnapshot) == 0
        batch = session.get(ImportBatch, "batch-failed")
        assert batch is not None
        assert batch.cursor_after is None
        assert session.get(SourceImportState, "source-hermes") is None
        session.rollback()

        retry = import_hermes(
            settings,
            session,
            _request(
                source_path,
                "batch-retry",
                "attempt-retry",
                dt.datetime(2026, 9, 19, 12, 1, tzinfo=dt.UTC),
            ),
        )
        assert retry.outcome == "succeeded"
        assert _count(session, NativeSnapshot) == 1
    finally:
        session.close()
        engine.dispose()


def test_import_rejects_a_caller_owned_transaction(tmp_path: Path) -> None:
    source_path, settings, session, engine = _context(tmp_path)
    try:
        session.begin()
        with pytest.raises(HermesImportError, match="idle"):
            import_hermes(
                settings,
                session,
                _request(
                    source_path,
                    "batch-active",
                    "attempt-active",
                    dt.datetime(2026, 9, 19, 12, 0, tzinfo=dt.UTC),
                ),
            )
        assert session.in_transaction()
    finally:
        session.rollback()
        session.close()
        engine.dispose()


def test_source_read_failure_is_durable_and_does_not_expose_path(
    tmp_path: Path,
) -> None:
    _, settings, session, engine = _context(tmp_path)
    missing = tmp_path / "private-source.db"
    try:
        result = import_hermes(
            settings,
            session,
            _request(
                missing,
                "batch-failed",
                "attempt-failed",
                dt.datetime(2026, 9, 19, 12, 0, tzinfo=dt.UTC),
            ),
        )

        assert result.outcome == "failed"
        assert result.error_summary == "Hermes source read failed"
        assert str(missing) not in result.error_summary
        batch = session.get(ImportBatch, "batch-failed")
        assert batch is not None
        assert batch.error_summary == "Hermes source read failed"
    finally:
        session.close()
        engine.dispose()
