"""Synthetic Pi and ChatGPT file-source contract checks."""

from __future__ import annotations

import json
from pathlib import Path
import zipfile

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from benchwarmer.adapters.chatgpt.reader import (
    import_chatgpt_export,
    read_chatgpt_export,
)
from benchwarmer.adapters.file_conversations import FileConversationError
from benchwarmer.adapters.pi.reader import (
    import_pi_directory,
    import_pi_session,
    read_pi_directory,
    read_pi_session,
)
from benchwarmer.config import BenchwarmerSettings
from benchwarmer.conversations import validate_conversation
from benchwarmer.models import (
    Base,
    ConversationRevision,
    NativeMessage,
    NativeSnapshot,
    Source,
    SourceImportState,
)


def _pi_file(path: Path, *, edited: bool = False) -> Path:
    rows = [
        {
            "type": "session",
            "version": 3,
            "id": "pi-session",
            "timestamp": "2026-01-01T00:00:00Z",
            "cwd": "/private/example",
        },
        {
            "type": "message",
            "id": "u1",
            "parentId": None,
            "timestamp": "2026-01-01T00:00:01Z",
            "message": {"role": "user", "content": "question"},
        },
        {
            "type": "message",
            "id": "a1",
            "parentId": "u1",
            "timestamp": "2026-01-01T00:00:02Z",
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "revised" if edited else "answer"}
                ],
                "usage": {"input": 3, "output": 1, "cost": {"total": 0.01}},
            },
        },
        {
            "type": "message",
            "id": "a2",
            "parentId": "u1",
            "timestamp": "2026-01-01T00:00:03Z",
            "message": {"role": "assistant", "content": "alternative"},
        },
    ]
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
    return path


def _pi_v1_log(path: Path) -> Path:
    rows = [
        {
            "version": 1,
            "runId": "run-one",
            "recordType": "message",
            "sourceEventType": "initial_prompt",
            "role": "user",
            "text": "prompt",
            "timestamp": "2026-01-01T00:00:00Z",
        },
        {
            "version": 1,
            "runId": "run-one",
            "recordType": "message",
            "sourceEventType": "message_end",
            "role": "assistant",
            "text": "answer",
            "timestamp": "2026-01-01T00:00:01Z",
            "usage": {"input": 2},
        },
    ]
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
    return path


def _chat_export(path: Path) -> Path:
    records = [
        {
            "id": "chat-one",
            "title": "Synthetic chat",
            "current_node": "a2",
            "mapping": {
                "root": {"parent": None, "message": None},
                "u1": {
                    "parent": "root",
                    "message": {
                        "author": {"role": "user"},
                        "create_time": 1767225601,
                        "content": {"content_type": "text", "parts": ["hello"]},
                    },
                },
                "a1": {
                    "parent": "u1",
                    "message": {
                        "author": {"role": "assistant"},
                        "create_time": 1767225602,
                        "content": {"content_type": "text", "parts": ["one"]},
                    },
                },
                "a2": {
                    "parent": "u1",
                    "message": {
                        "author": {"role": "assistant"},
                        "create_time": 1767225603,
                        "content": {"content_type": "text", "parts": ["two"]},
                    },
                },
            },
        }
    ]
    path.write_text(json.dumps(records))
    return path


@pytest.fixture
def database(tmp_path: Path):
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'benchwarmer.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add_all(
            [
                Source(
                    id="pi-source",
                    kind="pi",
                    scope_id="synthetic-pi",
                    display_name="Pi",
                ),
                Source(
                    id="chat-source",
                    kind="chatgpt",
                    scope_id="synthetic-chat",
                    display_name="ChatGPT",
                ),
            ]
        )
        session.commit()
    yield engine
    engine.dispose()


def test_pi_import_retains_tree_and_revisions(tmp_path: Path, database) -> None:
    path = _pi_file(tmp_path / "session.jsonl")
    settings = BenchwarmerSettings(data_root=tmp_path / "private")
    item = read_pi_session(path)
    assert [event["parent_id"] for event in item.events] == [None, "u1", "u1"]
    with Session(database) as session:
        first = import_pi_session(
            settings,
            session,
            source_id="pi-source",
            path=path,
            batch_id="pi-batch-1",
            idempotency_key="pi-1",
        )
        assert first.revisions == 1
        assert (
            import_pi_session(
                settings,
                session,
                source_id="pi-source",
                path=path,
                batch_id="ignored",
                idempotency_key="pi-1",
            ).revisions
            == 0
        )
        assert session.scalar(select(func.count()).select_from(NativeMessage)) == 3
        session.rollback()
        _pi_file(path, edited=True)
        second = import_pi_session(
            settings,
            session,
            source_id="pi-source",
            path=path,
            batch_id="pi-batch-2",
            idempotency_key="pi-2",
        )
        assert second.revisions == 1
        docs = list(
            session.scalars(
                select(ConversationRevision).where(
                    ConversationRevision.source_id == "pi-source"
                )
            )
        )
        assert len(docs) == 2
        assert session.scalar(select(func.count()).select_from(NativeSnapshot)) == 2
        for row in docs:
            validate_conversation(row.document)
        snapshots = list(session.scalars(select(NativeSnapshot)))
        assert all(
            (settings.data_root / row.relative_path).is_file() for row in snapshots
        )


def test_pi_directory_imports_each_session_once(tmp_path: Path, database) -> None:
    directory = tmp_path / "sessions"
    directory.mkdir()
    first = _pi_file(directory / "one.jsonl")
    second = directory / "two.jsonl"
    second.write_text(first.read_text().replace("pi-session", "pi-session-two"))
    _pi_v1_log(directory / "legacy.jsonl")
    assert len(read_pi_directory(directory)) == 3
    with Session(database) as session:
        result = import_pi_directory(
            BenchwarmerSettings(data_root=tmp_path / "private"),
            session,
            source_id="pi-source",
            path=directory,
            batch_id="pi-directory-batch",
            idempotency_key="pi-directory-1",
        )
        assert result.conversations == 3
        assert result.revisions == 3
        state = session.get(SourceImportState, "pi-source")
        assert state is not None
        assert state.schema_version == 0
        assert state.cursor["value"]["source_schema_versions"] == [1, 3]
        legacy = session.scalar(
            select(ConversationRevision).where(
                ConversationRevision.native_id == "run-one"
            )
        )
        assert legacy is not None
        assert legacy.document["coverage"]["messages"] == "partial"
        validate_conversation(legacy.document)


def test_chatgpt_export_zip_imports_branches(tmp_path: Path, database) -> None:
    json_path = _chat_export(tmp_path / "conversations.json")
    archive_path = tmp_path / "export.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.write(json_path, arcname="conversations.json")
    items = read_chatgpt_export(archive_path)
    assert len(items) == 1
    assert [event["parent_id"] for event in items[0].events] == [
        None,
        "root",
        "u1",
        "u1",
    ]
    with Session(database) as session:
        result = import_chatgpt_export(
            BenchwarmerSettings(data_root=tmp_path / "private"),
            session,
            source_id="chat-source",
            path=archive_path,
            batch_id="chat-batch",
            idempotency_key="chat-1",
        )
        assert result.revisions == 1
        revision = session.scalar(
            select(ConversationRevision).where(
                ConversationRevision.source_id == "chat-source"
            )
        )
        assert revision is not None
        validate_conversation(revision.document)
        assert revision.document["coverage"]["usage"] == "unknown"


def test_readers_fail_closed_on_unsupported_inputs(tmp_path: Path) -> None:
    path = _pi_file(tmp_path / "session.jsonl")
    path.write_text(path.read_text().replace('"version": 3', '"version": 99'))
    with pytest.raises(FileConversationError, match="unsupported"):
        read_pi_session(path)
    chat = _chat_export(tmp_path / "conversations.json")
    data = json.loads(chat.read_text())
    data[0]["mapping"]["u1"]["parent"] = "a1"
    chat.write_text(json.dumps(data))
    with pytest.raises(FileConversationError, match="cycle"):
        read_chatgpt_export(chat)
