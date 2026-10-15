"""Conversation browsing and keyword search over synthetic imports."""

from __future__ import annotations

import datetime as dt
import os
from pathlib import Path
import subprocess

from fastapi.testclient import TestClient

from benchwarmer.adapters.file_conversations import (
    FileConversation,
    import_file_conversations,
)
from benchwarmer.api.app import create_app
from benchwarmer.config import BenchwarmerSettings
from benchwarmer.db import create_engine, create_session_factory
from benchwarmer.models import Source

_REPOSITORY_ROOT = Path(__file__).parents[2]


def _migrated_settings(tmp_path: Path) -> BenchwarmerSettings:
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


def _block(kind: str, text: str | None, tool_call_id: str | None = None) -> dict:
    return {
        "kind": kind,
        "text": text,
        "tool_call_id": tool_call_id,
        "artifact_id": None,
        "extensions": {},
    }


def _event(
    native_id: str,
    ordinal: int,
    parent: str | None,
    role: str,
    blocks: list[dict],
    occurred_at: str | None,
) -> dict[str, object]:
    return {
        "native_id": native_id,
        "ordinal": ordinal,
        "parent_id": parent,
        "kind": "message",
        "role": role,
        "occurred_at": occurred_at,
        "content": blocks,
        "extensions": {},
    }


def _refund(answer: str) -> FileConversation:
    return FileConversation(
        native_id="refund-session",
        native={"id": "refund-session"},
        events=(
            _event(
                "u1",
                0,
                None,
                "user",
                [_block("text", "I need a refund for the second item.")],
                "2026-03-01T10:42:00Z",
            ),
            _event(
                "a1",
                1,
                "u1",
                "assistant",
                [
                    _block("text", answer),
                    _block("tool_call", '{"order": 42}', "call-1"),
                ],
                "2026-03-01T10:43:00+00:00",
            ),
            _event(
                "t1",
                2,
                "a1",
                "tool",
                [_block("tool_result", "Order found; item names differ.", "call-1")],
                "2026-03-01T10:44:00Z",
            ),
            _event(
                "a2",
                3,
                "u1",
                "assistant",
                [_block("text", "I can offer a replacement instead.")],
                "2026-03-01T11:18:00Z",
            ),
        ),
        metadata=(("title", "Refund investigation"),),
    )


def _hermes_pair() -> tuple[FileConversation, ...]:
    parent = FileConversation(
        native_id="h-parent",
        native={"id": "h-parent"},
        events=(
            _event(
                "p1", 0, None, "user", [_block("text", "Plan the migration.")], None
            ),
            _event("p2", 1, "p1", "assistant", [_block("text", "Step one.")], None),
        ),
        coverage={"messages": "partial", "tool_calls": "unknown"},
    )
    child = FileConversation(
        native_id="h-child",
        native={"id": "h-child"},
        events=(
            _event(
                "c1",
                0,
                None,
                "user",
                [_block("text", "Continue the migration.")],
                "2026-01-05T09:00:00Z",
            ),
        ),
        relationships=(
            {
                "kind": "continuation",
                "target_source_kind": "hermes",
                "target_source_scope_id": "profile-a",
                "target_native_id": "h-parent",
                "extensions": {},
            },
        ),
    )
    return parent, child


def _library(tmp_path: Path) -> BenchwarmerSettings:
    settings = _migrated_settings(tmp_path)
    engine = create_engine(settings)
    factory = create_session_factory(engine)
    try:
        with factory() as session:
            session.add_all(
                [
                    Source(
                        id="src-pi",
                        kind="pi",
                        scope_id="workspace-a",
                        display_name="Synthetic Pi",
                    ),
                    Source(
                        id="src-hermes",
                        kind="hermes",
                        scope_id="profile-a",
                        display_name="Synthetic Hermes",
                    ),
                ]
            )
            session.commit()
        with factory() as session:
            import_file_conversations(
                settings,
                session,
                source_id="src-pi",
                source_kind="pi",
                batch_id="batch-pi-1",
                idempotency_key="pi-1",
                items=(_refund("Checking the refund policy."),),
                adapter_version="test-1",
                captured_at=dt.datetime(2026, 3, 2, tzinfo=dt.UTC),
            )
        with factory() as session:
            import_file_conversations(
                settings,
                session,
                source_id="src-pi",
                source_kind="pi",
                batch_id="batch-pi-2",
                idempotency_key="pi-2",
                items=(_refund("Checking the refund policy and order history."),),
                adapter_version="test-1",
                captured_at=dt.datetime(2026, 3, 3, tzinfo=dt.UTC),
            )
        with factory() as session:
            import_file_conversations(
                settings,
                session,
                source_id="src-hermes",
                source_kind="hermes",
                batch_id="batch-hermes-1",
                idempotency_key="hermes-1",
                items=_hermes_pair(),
                adapter_version="test-1",
                captured_at=dt.datetime(2026, 1, 6, tzinfo=dt.UTC),
            )
    finally:
        engine.dispose()
    return settings


def _ids_by_native(client: TestClient) -> dict[str, str]:
    body = client.get("/api/v1/conversations").json()
    return {item["native_id"]: item["id"] for item in body["items"]}


def test_conversations_returns_a_stable_empty_envelope(tmp_path: Path) -> None:
    client = TestClient(create_app(_migrated_settings(tmp_path)))

    response = client.get("/api/v1/conversations")

    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "limit": 50, "offset": 0}


def test_list_shows_latest_revisions_by_recent_activity(tmp_path: Path) -> None:
    client = TestClient(create_app(_library(tmp_path)))

    body = client.get("/api/v1/conversations").json()

    assert body["total"] == 3
    assert [item["native_id"] for item in body["items"]] == [
        "refund-session",
        "h-child",
        "h-parent",
    ]
    refund = body["items"][0]
    assert refund["title"] == "Refund investigation"
    assert refund["preview"] == "I need a refund for the second item."
    assert refund["source"] == {
        "id": "src-pi",
        "kind": "pi",
        "display_name": "Synthetic Pi",
    }
    assert refund["captured_at"] == "2026-03-03T00:00:00Z"
    assert refund["started_at"] == "2026-03-01T10:42:00Z"
    assert refund["last_activity_at"] == "2026-03-01T11:18:00Z"
    assert refund["event_count"] == 4
    assert refund["message_count"] == 4
    assert refund["branch_count"] == 2
    assert refund["match_count"] == 0
    assert refund["matches"] == []

    parent = body["items"][2]
    assert parent["title"] is None
    assert parent["started_at"] is None
    assert parent["last_activity_at"] is None
    assert parent["coverage"] == {"messages": "partial", "tool_calls": "unknown"}
    assert body["items"][1]["relationship_counts"] == {"continuation": 1}


def test_list_filters_by_source_and_paginates(tmp_path: Path) -> None:
    client = TestClient(create_app(_library(tmp_path)))

    hermes = client.get("/api/v1/conversations", params={"source_kind": "hermes"})
    page = client.get("/api/v1/conversations", params={"limit": 1, "offset": 1})
    pi = client.get("/api/v1/conversations", params={"source_id": "src-pi"})

    assert [item["native_id"] for item in hermes.json()["items"]] == [
        "h-child",
        "h-parent",
    ]
    assert page.json()["total"] == 3
    assert [item["native_id"] for item in page.json()["items"]] == ["h-child"]
    assert [item["native_id"] for item in pi.json()["items"]] == ["refund-session"]
    assert client.get("/api/v1/conversations", params={"limit": 0}).status_code == 422


def test_search_returns_anchored_case_insensitive_matches(tmp_path: Path) -> None:
    client = TestClient(create_app(_library(tmp_path)))

    body = client.get("/api/v1/conversations", params={"q": "REFUND"}).json()

    assert [item["native_id"] for item in body["items"]] == ["refund-session"]
    refund = body["items"][0]
    # Title, the user message, and the latest assistant answer all match.
    assert refund["match_count"] == 3
    assert [hit["field"] for hit in refund["matches"]] == ["title", "text", "text"]
    assert refund["matches"][0]["event_id"] is None
    user_hit = refund["matches"][1]
    assert user_hit["event_id"] == f"{refund['id']}:event:u1"
    assert user_hit["block_id"] == f"{refund['id']}:event:u1:block:0"
    assert user_hit["snippet"] == "I need a refund for the second item."

    tool = client.get("/api/v1/conversations", params={"q": "item names"}).json()
    assert tool["items"][0]["matches"][0]["field"] == "tool_result"

    none = client.get("/api/v1/conversations", params={"q": "nonexistent"}).json()
    assert none == {"items": [], "total": 0, "limit": 50, "offset": 0}


def test_search_matches_only_the_latest_revision(tmp_path: Path) -> None:
    client = TestClient(create_app(_library(tmp_path)))

    body = client.get("/api/v1/conversations", params={"q": "order history"}).json()

    assert [item["native_id"] for item in body["items"]] == ["refund-session"]


def test_detail_returns_events_branches_and_revisions(tmp_path: Path) -> None:
    client = TestClient(create_app(_library(tmp_path)))
    conversation_id = _ids_by_native(client)["refund-session"]

    response = client.get(f"/api/v1/conversations/{conversation_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["is_latest"] is True
    assert [item["captured_at"] for item in body["revisions"]] == [
        "2026-03-03T00:00:00Z",
        "2026-03-02T00:00:00Z",
    ]
    assert body["summary"]["revision"] == body["revisions"][0]["revision"]
    assert [event["native_id"] for event in body["events"]] == ["u1", "a1", "t1", "a2"]
    assert body["events"][1]["occurred_at"] == "2026-03-01T10:43:00+00:00"
    assert body["events"][1]["content"][1]["kind"] == "tool_call"
    assert body["metadata"][0]["name"] == "title"
    assert body["metadata"][0]["origin"] == "imported"

    event = f"{conversation_id}:event:"
    assert body["branches"] == [
        {
            "id": f"{event}t1",
            "leaf_event_id": f"{event}t1",
            "event_ids": [f"{event}u1", f"{event}a1", f"{event}t1"],
            "fork_event_id": f"{event}u1",
        },
        {
            "id": f"{event}a2",
            "leaf_event_id": f"{event}a2",
            "event_ids": [f"{event}u1", f"{event}a2"],
            "fork_event_id": f"{event}u1",
        },
    ]


def test_detail_can_read_an_earlier_revision(tmp_path: Path) -> None:
    client = TestClient(create_app(_library(tmp_path)))
    conversation_id = _ids_by_native(client)["refund-session"]
    revisions = client.get(f"/api/v1/conversations/{conversation_id}").json()[
        "revisions"
    ]

    earlier = client.get(
        f"/api/v1/conversations/{conversation_id}",
        params={"revision": revisions[1]["revision"]},
    )
    missing = client.get(
        f"/api/v1/conversations/{conversation_id}", params={"revision": "nope"}
    )

    assert earlier.status_code == 200
    body = earlier.json()
    assert body["is_latest"] is False
    assert body["events"][1]["content"][0]["text"] == "Checking the refund policy."
    assert missing.status_code == 404


def test_detail_resolves_continuations_in_both_directions(tmp_path: Path) -> None:
    client = TestClient(create_app(_library(tmp_path)))
    ids = _ids_by_native(client)

    child = client.get(f"/api/v1/conversations/{ids['h-child']}").json()
    parent = client.get(f"/api/v1/conversations/{ids['h-parent']}").json()

    assert child["relationships"] == [
        {
            "kind": "continuation",
            "target_source_kind": "hermes",
            "target_source_scope_id": "profile-a",
            "target_native_id": "h-parent",
            "target_conversation_id": ids["h-parent"],
            "extensions": {},
        }
    ]
    assert child["referenced_by"] == []
    assert parent["relationships"] == []
    assert parent["referenced_by"] == [
        {"kind": "continuation", "conversation_id": ids["h-child"]}
    ]
    assert len(parent["branches"]) == 1


def test_detail_reports_unknown_conversations(tmp_path: Path) -> None:
    client = TestClient(create_app(_migrated_settings(tmp_path)))

    response = client.get("/api/v1/conversations/conversation-missing")

    assert response.status_code == 404
    assert response.json() == {"detail": "Conversation not found"}
