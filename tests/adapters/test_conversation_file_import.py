"""Conversation files persist through the shared file-source path."""

from __future__ import annotations

import json
from pathlib import Path
import shutil

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from benchwarmer.adapters.conversation_file.reader import (
    import_conversation_path,
    read_conversation_file,
    read_conversation_files,
)
from benchwarmer.adapters.file_conversations import FileConversationError
from benchwarmer.config import BenchwarmerSettings
from benchwarmer.conversations import validate_conversation
from benchwarmer.models import (
    Base,
    ConversationRevision,
    NativeMessage,
    NativeSnapshot,
    Source,
)

_FIXTURES = Path(__file__).parents[1] / "fixtures/conversation-files/valid"


@pytest.fixture
def database(tmp_path: Path):
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'benchwarmer.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add_all(
            [
                Source(
                    id="files-a",
                    kind="conversation_file",
                    scope_id="synthetic-tenant-a",
                    display_name="Files A",
                ),
                Source(
                    id="files-b",
                    kind="conversation_file",
                    scope_id="synthetic-tenant-b",
                    display_name="Files B",
                ),
            ]
        )
        session.commit()
    yield engine
    engine.dispose()


def test_import_file_then_changed_file_yields_a_new_revision(
    tmp_path: Path, database
) -> None:
    settings = BenchwarmerSettings(data_root=tmp_path / "private")
    path = tmp_path / "conv.json"
    shutil.copy(_FIXTURES / "agent-product-log.json", path)
    with Session(database) as session:
        first = import_conversation_path(
            settings,
            session,
            source_id="files-a",
            path=path,
            batch_id="batch-1",
            idempotency_key="k1",
        )
        assert (first.conversations, first.revisions, first.snapshots) == (1, 1, 1)
        [imported] = first.items
        assert imported.native_id == "synthetic-conv-0001"
        assert imported.new_revision

        # Same content, new key: nothing new is stored.
        again = import_conversation_path(
            settings,
            session,
            source_id="files-a",
            path=path,
            batch_id="batch-2",
            idempotency_key="k2",
        )
        assert (again.revisions, again.snapshots) == (0, 0)
        assert again.items[0].revision == imported.revision
        assert not again.items[0].new_revision

        document = json.loads(path.read_text())
        document["events"][-1]["content"][0]["text"] = "Renamed; 13 tests pass."
        path.write_text(json.dumps(document))
        third = import_conversation_path(
            settings,
            session,
            source_id="files-a",
            path=path,
            batch_id="batch-3",
            idempotency_key="k3",
        )
        assert third.revisions == 1
        assert third.items[0].revision != imported.revision
        assert third.items[0].conversation_id == imported.conversation_id

        rows = list(session.scalars(select(ConversationRevision)))
        assert len(rows) == 2
        for row in rows:
            validate_conversation(row.document)
            assert row.document["source"]["kind"] == "conversation_file"
            assert row.document["extensions"]["tool_definitions"]
        assert session.scalar(select(func.count()).select_from(NativeMessage)) == 7
        snapshots = list(session.scalars(select(NativeSnapshot)))
        assert len(snapshots) == 2
        for snapshot in snapshots:
            stored = json.loads(
                (settings.data_root / snapshot.relative_path).read_text()
            )
            assert stored["format"] == "benchwarmer-conversation-file"


def test_directory_import_and_scope_checks(tmp_path: Path, database) -> None:
    settings = BenchwarmerSettings(data_root=tmp_path / "private")
    folder = tmp_path / "inbox"
    folder.mkdir()
    shutil.copy(_FIXTURES / "minimal.json", folder / "one.json")
    shutil.copy(_FIXTURES / "branches-and-gaps.json", folder / "nested.json")
    assert len(read_conversation_files(folder)) == 2
    with Session(database) as session:
        result = import_conversation_path(
            settings,
            session,
            source_id="files-b",
            path=folder,
            batch_id="dir-1",
            idempotency_key="dir-1",
        )
        assert result.conversations == 2
        with pytest.raises(FileConversationError, match="scope_id"):
            import_conversation_path(
                settings,
                session,
                source_id="files-a",
                path=folder,
                batch_id="dir-2",
                idempotency_key="dir-2",
            )
        with pytest.raises(FileConversationError, match="not found"):
            import_conversation_path(
                settings,
                session,
                source_id="nope",
                path=folder,
                batch_id="dir-3",
                idempotency_key="dir-3",
            )

    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(FileConversationError, match="no conversation files"):
        read_conversation_files(empty)
    duplicate = tmp_path / "dup"
    duplicate.mkdir()
    shutil.copy(_FIXTURES / "minimal.json", duplicate / "a.json")
    shutil.copy(_FIXTURES / "minimal.json", duplicate / "b.json")
    with pytest.raises(FileConversationError, match="repeat"):
        read_conversation_files(duplicate)


def test_unreadable_files_fail_closed_without_content(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text(
        '{"format": "benchwarmer-conversation-file", "secret": "sk-abcdefghijkl"}'
    )
    with pytest.raises(FileConversationError) as error:
        read_conversation_file(bad)
    assert "sk-abcdefghijkl" not in str(error.value)
    assert "$.secret" in str(error.value)
    link = tmp_path / "link.json"
    link.symlink_to(_FIXTURES / "minimal.json")
    with pytest.raises(FileConversationError, match="unusable"):
        read_conversation_file(link)
    with pytest.raises(FileConversationError, match="unusable"):
        read_conversation_file(Path("relative.json"))
