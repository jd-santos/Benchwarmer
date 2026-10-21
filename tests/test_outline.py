"""Deterministic outlines over synthetic events: headings, tools, segments."""

from __future__ import annotations

from typing import Any

from benchwarmer.outline import PathSpec, build_outline, find_headings


def _block(
    event_id: str,
    index: int,
    kind: str,
    text: str | None,
    *,
    tool_call_id: str | None = None,
) -> dict[str, Any]:
    return {
        "id": f"{event_id}:block:{index}",
        "kind": kind,
        "text": text,
        "tool_call_id": tool_call_id,
        "artifact_id": None,
        "extensions": {},
    }


def _event(
    event_id: str,
    ordinal: int,
    parent: str | None,
    kind: str,
    role: str,
    content: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "id": event_id,
        "native_id": f"native-{event_id}",
        "ordinal": ordinal,
        "parent_id": parent,
        "kind": kind,
        "role": role,
        "occurred_at": None,
        "content": content,
        "extensions": {},
    }


def test_find_headings_uses_code_point_ranges_and_strips_closing_marks() -> None:
    text = "intro\r\n## Résumé ##\nbody\n#not a heading\n### Deep  \n"
    headings = find_headings(text, "b")

    assert [(h.level, h.label) for h in headings] == [(2, "Résumé"), (3, "Deep")]
    first, second = headings
    assert text[first.text_start : first.text_end] == "## Résumé ##"
    assert text[second.text_start : second.text_end] == "### Deep  "
    assert first.id == "b::h0" and second.id == "b::h1"


def test_outline_measures_events_and_splits_paths() -> None:
    events = [
        _event("s0", 0, None, "message", "system", [_block("s0", 0, "text", "rules")]),
        _event("u1", 1, "s0", "message", "user", [_block("u1", 0, "text", "Fix it")]),
        _event(
            "a2",
            2,
            "u1",
            "message",
            "assistant",
            [
                _block("a2", 0, "reasoning", "hmm"),
                _block("a2", 1, "text", "# Plan\nRun tests"),
                _block("a2", 2, "tool_call", "bash", tool_call_id="call-1"),
                _block(
                    "a2", 3, "tool_call", '{"command": "ls"}', tool_call_id="call-2"
                ),
            ],
        ),
        _event(
            "t3",
            3,
            "a2",
            "message",
            "tool",
            [_block("t3", 0, "tool_result", None, tool_call_id="call-1")],
        ),
        _event("c4", 4, "t3", "compaction", "unknown", []),
        _event("u5", 5, "c4", "message", "user", [_block("u5", 0, "text", "Again")]),
        _event(
            "a6", 6, "u5", "message", "assistant", [_block("a6", 0, "text", "Done")]
        ),
        _event(
            "a7", 7, "u5", "message", "assistant", [_block("a7", 0, "text", "Other")]
        ),
    ]
    paths = [
        PathSpec(
            id="a6",
            leaf_event_id="a6",
            event_ids=["s0", "u1", "a2", "t3", "c4", "u5", "a6"],
            fork_event_id="u5",
            divergent_event_id="a6",
            is_original=True,
        ),
        PathSpec(
            id="a7",
            leaf_event_id="a7",
            event_ids=["s0", "u1", "a2", "t3", "c4", "u5", "a7"],
            fork_event_id="u5",
            divergent_event_id="a7",
            is_original=False,
        ),
    ]

    outline = build_outline(
        conversation_id="conv",
        revision="rev",
        events=events,
        paths=paths,
        coverage={"tool_calls": "partial"},
    )

    assert outline.event_count == 8 and outline.schema_version == 1
    by_id = {event.id: event for event in outline.events}
    reply = by_id["a2"]
    assert reply.text_chars == len("# Plan\nRun tests")
    assert reply.reasoning_chars == 3 and reply.text_captured is True
    assert reply.block_counts == {"reasoning": 1, "text": 1, "tool_call": 2}
    assert [(t.tool_call_id, t.tool_name) for t in reply.tools] == [
        ("call-1", "bash"),
        ("call-2", None),
    ]
    assert [h.label for h in reply.headings] == ["Plan"]
    assert reply.preview == "# Plan Run tests"
    result = by_id["t3"]
    assert result.text_captured is False and result.tools[0].chars is None
    assert by_id["c4"].boundary == "compaction" and by_id["c4"].preview is None

    original = outline.paths[0]
    assert original.is_original is True and original.fork_event_id == "u5"
    assert [x.user_event_id for x in original.exchanges] == [None, "u1", "u5"]
    assert original.exchanges[1].event_ids == ["u1", "a2", "t3", "c4"]
    assert original.exchanges[1].tool_call_count == 2
    assert original.exchanges[1].heading_count == 1
    assert original.exchanges[2].assistant_text_chars == 4
    assert [(s.opened_by, s.closed_by, s.event_ids) for s in original.segments] == [
        ("start", "compaction", ["s0", "u1", "a2", "t3"]),
        ("compaction", "end", ["u5", "a6"]),
    ]
    assert outline.paths[1].segments[1].event_ids == ["u5", "a7"]
    assert outline.coverage == {"tool_calls": "partial"}
    assert outline.notes
