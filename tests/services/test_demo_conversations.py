"""The synthetic demo library imports cleanly through the file importer."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess

from benchwarmer.config import BenchwarmerSettings
from benchwarmer.db import create_engine, create_session_factory
from benchwarmer.services.conversation_library import (
    get_conversation,
    list_conversations,
)
from benchwarmer.services.demo_conversations import load_demo_conversations
from benchwarmer.services.fixtures import load_fixture

_REPOSITORY_ROOT = Path(__file__).parents[2]


def _settings(tmp_path: Path) -> BenchwarmerSettings:
    root = tmp_path / "private"
    result = subprocess.run(
        ["uv", "run", "alembic", "upgrade", "head"],
        cwd=_REPOSITORY_ROOT,
        env=os.environ | {"BENCHWARMER_DATA_ROOT": str(root)},
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    return BenchwarmerSettings(data_root=root)


def test_demo_library_covers_browsing_states(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    load_fixture(settings, _REPOSITORY_ROOT / "tests/fixtures/sources.json")
    fixture = _REPOSITORY_ROOT / "tests/fixtures/demo-conversations.json"

    assert load_demo_conversations(settings, fixture) == 6
    assert load_demo_conversations(settings, fixture) == 0

    engine = create_engine(settings)
    try:
        with create_session_factory(engine)() as session:
            page = list_conversations(session)
            assert page.total == 5
            by_native = {item.native_id: item for item in page.items}
            long = get_conversation(session, by_native["demo-import-duplicates"].id)
            parent = get_conversation(session, by_native["demo-migration-1"].id)
    finally:
        engine.dispose()

    assert len(long.revisions) == 2
    assert len(long.branches) == 2
    assert any(event["kind"] == "compaction" for event in long.events)
    assert by_native["demo-migration-1"].last_activity_at is None
    assert [item.kind for item in parent.referenced_by] == ["continuation"]
    assert by_native["demo-model-switch"].event_count == 5
