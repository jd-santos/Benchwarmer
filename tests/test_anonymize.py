"""Scrubbing, fidelity, and leak checks over synthetic events only."""

from __future__ import annotations

import json
from typing import Any

from pathlib import Path

from benchwarmer.adapters.pi.reader import read_pi_session
from benchwarmer.anonymize import (
    FixtureConversation,
    Scrubber,
    fidelity_issues,
    fixture_conversation,
    leak_issues,
    scrub_conversation,
    scrub_file_conversation,
)

_SESSION = Path(__file__).parent / "fixtures" / "pi-session-synthetic.jsonl"


def _block(
    event_id: str,
    index: int,
    kind: str,
    text: str | None,
    *,
    tool_call_id: str | None = None,
    extensions: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "id": f"{event_id}:block:{index}",
        "kind": kind,
        "text": text,
        "tool_call_id": tool_call_id,
        "artifact_id": None,
        "extensions": extensions or {},
    }


def _event(
    native_id: str,
    ordinal: int,
    parent: str | None,
    kind: str,
    role: str,
    content: list[dict[str, Any]],
    extensions: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "id": f"conv:event:{native_id}",
        "native_id": native_id,
        "ordinal": ordinal,
        "parent_id": f"conv:event:{parent}" if parent else None,
        "kind": kind,
        "role": role,
        "occurred_at": "2026-10-02T09:00:00Z",
        "content": content,
        "extensions": extensions or {},
    }


_USER_TEXT = (
    "Ask Dana Example (dana@example-corp.com) why https://git.example-corp.com/x/y "
    "fails on 10.0.0.7 and fe80::1 with token sk-abcdefghijklmnop, "
    "see /Users/dana/projects/widget/src/main.py and ~/notes/todo.md"
)


def _events() -> list[dict[str, Any]]:
    return [
        _event("u0", 0, None, "message", "user", [_block("u0", 0, "text", _USER_TEXT)]),
        _event(
            "a0",
            1,
            "u0",
            "message",
            "assistant",
            [
                _block("a0", 0, "reasoning", "Dana's box is build.example-corp.com."),
                _block(
                    "a0",
                    1,
                    "tool_call",
                    json.dumps({"command": "ssh dana@10.0.0.7 cat /etc/hosts/extra"}),
                    tool_call_id="call-0",
                ),
            ],
        ),
        _event(
            "t0",
            2,
            "a0",
            "message",
            "tool",
            [
                _block(
                    "t0",
                    0,
                    "tool_result",
                    "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123 "
                    "0123456789abcdef0123456789abcdef01234567 ok",
                    tool_call_id="call-0",
                )
            ],
        ),
        _event(
            "c0",
            3,
            "t0",
            "configuration",
            "unknown",
            [],
            extensions={"pi_entry_type": "model_change"},
        ),
        _event(
            "t1",
            4,
            "c0",
            "message",
            "tool",
            [_block("t1", 0, "tool_result", None, tool_call_id="call-9")],
        ),
    ]


def _scrub(terms: list[str]):
    return scrub_conversation(
        native_id="native-1",
        source_version="session-v3",
        title="Dana Example fixes widget on build.example-corp.com",
        events=_events(),
        relationships=[{"kind": "continuation", "extensions": {}}],
        coverage={"messages": "available"},
        terms=terms,
    )


def test_scrub_replaces_each_category_with_stable_placeholders() -> None:
    result, scrubber = _scrub(["Dana Example", "widget"])
    text = result.events[0]["content"][0]["text"]

    assert "dana@example-corp.com" not in text
    assert "https://" not in text and "10.0.0.7" not in text and "fe80::1" not in text
    assert "sk-abcdefghijklmnop" not in text
    assert "/Users/dana" not in text and "~/notes" not in text
    assert "/scrubbed/path-1/file-1.py" in text
    assert "/scrubbed/path-2/file-2.md" in text
    assert text.startswith("Ask <term-1> (<email-1>) why <url-1> fails on <ipv4-1>")
    assert result.title == "<term-1> fixes <term-2> on <hostname-1>"
    # The same host and address reappear and keep their placeholders.
    assert result.events[1]["content"][0]["text"] == "Dana's box is <hostname-1>."
    call = json.loads(result.events[1]["content"][1]["text"])
    assert call["command"] == "ssh dana@<ipv4-1> cat /scrubbed/path-3/file-3"
    assert "<secret-2>" in result.events[2]["content"][0]["text"]
    assert "<secret-3>" in result.events[2]["content"][0]["text"]

    counts = result.report.counts
    assert counts["term"] == 3 and counts["hostname"] == 2 and counts["ipv4"] == 2
    assert counts["email"] == 1 and counts["url"] == 1 and counts["path"] == 3
    assert counts["secret"] == 3 and counts["ipv6"] == 1
    assert result.report.term_count == 2
    assert set(result.report.placeholders) == set(
        span.placeholder for span in result.report.spans
    )
    originals = scrubber.originals()
    assert "dana@example-corp.com" in originals
    assert not any(
        value in json.dumps(result.report.model_dump()) for value in originals
    )


def test_scrub_spans_locate_original_text_by_code_points() -> None:
    result, _ = _scrub(["Dana Example"])
    events = {event["id"]: event for event in _events()}
    for span in result.report.spans:
        if span.event_id is None:
            source = "Dana Example fixes widget on build.example-corp.com"
        else:
            blocks = {b["id"]: b for b in events[span.event_id]["content"]}
            source = blocks[span.block_id]["text"]
        original = source[span.text_start : span.text_end]
        assert original and original not in json.dumps(result.model_dump())


def test_scrub_preserves_everything_except_text() -> None:
    result, _ = _scrub([])
    for before, after in zip(_events(), result.events, strict=True):
        assert {k: v for k, v in before.items() if k != "content"} == {
            k: v for k, v in after.items() if k != "content"
        }
        for b, a in zip(before["content"], after["content"], strict=True):
            assert {k: v for k, v in b.items() if k != "text"} == {
                k: v for k, v in a.items() if k != "text"
            }
            assert (b["text"] is None) == (a["text"] is None)
    assert result.events[3]["extensions"] == {"pi_entry_type": "model_change"}
    assert result.fixture.events[1].parent_id == "u0"
    assert result.fixture.relationships == [{"kind": "continuation", "extensions": {}}]
    assert result.fixture.coverage == {"messages": "available"}


def test_term_matching_is_whole_word_and_case_insensitive() -> None:
    scrubber = Scrubber(["Acme", "jd"])
    out = scrubber.scrub_text(
        "ACME and acme but not acmeware; JD, jd and jdwork", event_id="e", block_id="b"
    )
    assert (
        out == "<term-1> and <term-1> but not acmeware; <term-2>, <term-2> and jdwork"
    )
    assert scrubber.counts == {"term": 4}


def test_plain_prose_is_left_alone() -> None:
    scrubber = Scrubber([])
    text = "Run pytest, then edit library.db and module.py; the ratio is 1.5."
    assert scrubber.scrub_text(text, event_id="e", block_id="b") == text
    assert scrubber.counts == {}


def test_fidelity_reports_structural_drift() -> None:
    result, _ = _scrub([])
    original = result.fixture
    assert fidelity_issues(original, original) == []

    broken = json.loads(original.model_dump_json())
    broken["events"].pop()
    broken["events"][1]["role"] = "user"
    broken["events"][1]["content"].pop(0)
    broken["events"][2]["content"][0]["tool_call_id"] = "other"
    broken["events"][3]["extensions"] = {}
    broken["relationships"] = []
    broken["title"] = None
    issues = fidelity_issues(original, FixtureConversation.model_validate(broken))
    codes = {issue.code for issue in issues}
    assert codes == {
        "event_count",
        "role",
        "block_kinds",
        "tool_pairing",
        "extension_keys",
        "relationship_kinds",
        "title_presence",
    }
    assert all(issue.message for issue in issues)


def test_fidelity_follows_parent_positions_not_names() -> None:
    result, _ = _scrub([])
    renamed = json.loads(result.fixture.model_dump_json())
    mapping = {e["native_id"]: f"x{i}" for i, e in enumerate(renamed["events"])}
    for event in renamed["events"]:
        event["native_id"] = mapping[event["native_id"]]
        if event["parent_id"] is not None:
            event["parent_id"] = mapping[event["parent_id"]]
    assert (
        fidelity_issues(result.fixture, FixtureConversation.model_validate(renamed))
        == []
    )

    renamed["events"][2]["parent_id"] = "x0"
    renamed["events"][4]["parent_id"] = "missing"
    issues = fidelity_issues(
        result.fixture, FixtureConversation.model_validate(renamed)
    )
    assert {issue.code for issue in issues} == {"parent", "unknown_parent"}


def test_leak_check_finds_terms_and_original_spans_without_repeating_them() -> None:
    result, scrubber = _scrub(["Dana Example"])
    clean = leak_issues(
        result.fixture, terms=["Dana Example"], originals=scrubber.originals()
    )
    assert clean == []

    leaked = json.loads(result.fixture.model_dump_json())
    leaked["events"][0]["content"][0]["text"] = (
        "mail DANA EXAMPLE at dana@example-corp.com"
    )
    leaked["events"][3]["extensions"]["pi_entry_type"] = (
        "https://git.example-corp.com/x/y"
    )
    issues = leak_issues(
        FixtureConversation.model_validate(leaked),
        terms=["Dana Example"],
        originals=scrubber.originals(),
    )
    assert [(i.code, i.location, i.category) for i in issues] == [
        ("term", "candidate.events[0].content[0].text", "term"),
        ("original_span", "candidate.events[0].content[0].text", "email"),
        ("original_span", "candidate.events[3].extensions.pi_entry_type", "url"),
    ]
    assert issues[0].text_start == 5 and issues[0].text_end == 17
    serialized = json.dumps([issue.model_dump() for issue in issues])
    assert "dana" not in serialized.lower() and "example-corp" not in serialized


def test_fixture_conversation_maps_parents_to_native_ids() -> None:
    fixture = fixture_conversation(
        native_id="n",
        title=None,
        events=_events(),
        relationships=[],
        coverage=None,
        usage=[{"entry_id": "a0", "provider": "synthetic", "model": "m"}],
    )
    assert [e.parent_id for e in fixture.events] == [None, "u0", "a0", "t0", "c0"]
    assert fixture.usage == [{"entry_id": "a0", "provider": "synthetic", "model": "m"}]
    assert "id" not in fixture.events[0].model_dump()


def test_scrub_file_conversation_covers_a_parsed_pi_session() -> None:
    item = read_pi_session(_SESSION.resolve())
    result, scrubber = scrub_file_conversation(item, terms=["Dana"])

    assert result.report.native_id == "synthetic-pi-anonymizer"
    assert result.report.source_version == "session-v3"
    assert result.title is None
    assert set(result.report.counts) == {
        "url",
        "path",
        "ipv4",
        "email",
        "secret",
        "term",
        "hostname",
    }
    serialized = result.model_dump_json()
    for original in scrubber.originals():
        assert original not in serialized
    assert "resp-0001" not in serialized
    assert result.fixture.usage[0]["entry_id"] == "a0"
    assert [e.native_id for e in result.fixture.events] == [
        e["native_id"] for e in item.events
    ]
    assert fidelity_issues(result.fixture, result.fixture) == []
    assert (
        leak_issues(result.fixture, terms=["Dana"], originals=scrubber.originals())
        == []
    )
