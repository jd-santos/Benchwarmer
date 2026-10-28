"""Conversation file v1: validation, conversion, builder, converter, and CLI."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from benchwarmer.conversations import validate_conversation
from benchwarmer.interchange import (
    ConversationFileBuilder,
    ConversationFileError,
    attachment_block,
    load_conversation_file,
    normalized_preview,
    provenance,
    text_block,
    to_file_conversation,
    tool_call_block,
    tool_result_block,
    validate_conversation_file,
)
from benchwarmer.interchange.agent_log import AgentLogError, convert_agent_log
from benchwarmer.interchange.cli import main

_ROOT = Path(__file__).parents[2]
_FIXTURES = _ROOT / "tests/fixtures/conversation-files"
_AGENT_LOG = _ROOT / "tests/fixtures/agent-logs/example-agent-log.json"


def _load(name: str) -> dict:
    return json.loads((_FIXTURES / name).read_text())


def test_agent_log_fixture_converts_to_the_checked_in_conversation_file() -> None:
    converted = convert_agent_log(json.loads(_AGENT_LOG.read_text()))
    assert converted == _load("valid/agent-product-log.json")
    with pytest.raises(AgentLogError):
        convert_agent_log({"log_format": "something-else"})


def test_agent_log_mapping_preserves_what_reconstruction_needs() -> None:
    document = _load("valid/agent-product-log.json")
    normalized = normalized_preview(document)
    validate_conversation(normalized)
    by_native = {event["native_id"]: event for event in normalized["events"]}

    # System prompt: a configuration event, and its hash on each model turn.
    prompt = by_native["system-prompt"]
    assert prompt["kind"] == "configuration" and prompt["role"] == "system"
    digest = by_native["t2"]["extensions"]["provenance"]["system_prompt_sha256"]
    assert len(digest) == 64
    assert by_native["t4"]["extensions"]["provenance"]["system_prompt_sha256"] == digest
    assert by_native["t2"]["extensions"]["provenance"]["params"] == {
        "temperature": 0.2,
        "max_tokens": 2048,
    }

    # Tool definitions and the linked call/result pair with its arguments.
    tools = normalized["extensions"]["tool_definitions"]
    assert [tool["name"] for tool in tools] == ["search_code", "read_file"]
    call = by_native["t2"]["content"][2]
    assert call["kind"] == "tool_call" and call["text"] == "search_code"
    assert call["extensions"]["tool_call"]["input"] == {"pattern": "enable_fast_sync"}
    result = by_native["t3"]["content"][0]
    assert result["tool_call_id"] == call["tool_call_id"] == "call-1"
    assert result["extensions"]["tool_result"]["is_error"] is False

    # Attached context: an artifact the user turn references.
    [artifact] = normalized["artifacts"]
    assert artifact["id"] == "context-att-1"
    assert artifact["availability"] == "available"
    assert artifact["extensions"]["context_item"]["name"] == "flag-notes.md"
    assert by_native["t1"]["content"][1]["artifact_id"] == "context-att-1"

    # The rewind is a sibling branch that supersedes the first attempt.
    assert by_native["t5"]["parent_id"] == by_native["t1"]["id"]
    assert by_native["t2"]["parent_id"] == by_native["t1"]["id"]
    assert by_native["t5"]["extensions"]["supersedes_native_id"] == "t2"

    # Feedback is a human-origin annotation; usage is an imported observation.
    names = {entry["name"]: entry for entry in normalized["metadata"]}
    assert names["annotation"]["origin"] == "human"
    assert names["annotation"]["value"]["event_native_id"] == "t4"
    assert names["usage_observations"]["origin"] == "imported"
    assert len(names["usage_observations"]["value"]) == 3
    assert names["title"]["value"].startswith("Rename")

    # Raw responses live in the snapshot, which is the whole file.
    item = to_file_conversation(document)
    assert item.native is document
    assert item.native["native"]["raw_responses"][0]["turn_id"] == "t2"
    assert item.coverage["tool_calls"] == "available"


def test_defaults_and_gaps_are_explicit() -> None:
    minimal = to_file_conversation(_load("valid/minimal.json"))
    assert minimal.coverage == {
        "messages": "available",
        "branches": "available",
        "usage": "unknown",
        "prompts": "unknown",
        "tool_calls": "partial",
    }
    assert [event["ordinal"] for event in minimal.events] == [0, 10]
    gaps = to_file_conversation(_load("valid/branches-and-gaps.json"))
    assert gaps.coverage["prompts"] == "unavailable"
    assert gaps.relationships[0]["target_source_kind"] == "conversation_file"
    assert dict(gaps.metadata)["channel"] == "web"
    assert dict(gaps.extensions)["writer"]["name"] == "synthetic-exporter"


def test_issues_name_json_paths_and_conversion_refuses_invalid_files() -> None:
    issues = validate_conversation_file(_load("invalid/bad-role.json"))
    assert [issue.path for issue in issues] == ["$.events[0].role"]
    many = validate_conversation_file({"format": "x", "events": "no"})
    assert {issue.path for issue in many} >= {
        "$.format",
        "$.format_version",
        "$.scope_id",
        "$.native_id",
        "$.events",
    }
    with pytest.raises(ConversationFileError) as error:
        to_file_conversation(_load("invalid/unknown-field.json"))
    assert "$.extra" in str(error.value)
    assert validate_conversation_file("not an object")[0].path == "$"


def test_builder_renders_a_valid_file() -> None:
    builder = ConversationFileBuilder(
        scope_id="synthetic-tenant-c", native_id="built-1", title="Built"
    )
    builder.add_tool("lookup", description="Look something up")
    builder.add_context("ctx-1", kind="file", name="a.txt", text="alpha")
    root = builder.add_system_prompt("sys", "Be brief.")
    user = builder.add_event(
        "u1",
        "user",
        [text_block("Look up alpha."), attachment_block("ctx-1")],
        parent_native_id=root,
        occurred_at="2026-01-01T00:00:00Z",
    )
    assistant = builder.add_event(
        "a1",
        "assistant",
        [tool_call_block("c1", "lookup", {"term": "alpha"})],
        parent_native_id=user,
        provenance=provenance("example-model", usage={"input_tokens": 3}),
    )
    builder.add_event(
        "r1", "tool", [tool_result_block("c1", {"hits": 1})], parent_native_id=assistant
    )
    builder.add_feedback(event_native_id="a1", rating=1, text="good", by="qa")
    builder.add_relationship(
        "continuation", target_scope_id="synthetic-tenant-c", target_native_id="built-0"
    )
    builder.add_metadata("channel", "test")
    document = builder.build()
    assert validate_conversation_file(document) == []
    normalized = normalized_preview(document)
    assert normalized["source"]["kind"] == "conversation_file"
    assert len(normalized["events"]) == 4

    builder.add_event("bad", "narrator", [])
    with pytest.raises(ConversationFileError):
        builder.build()


def test_cli_reports_issues_and_exit_codes(tmp_path: Path, capsys) -> None:
    valid = _FIXTURES / "valid/minimal.json"
    invalid = _FIXTURES / "invalid/bad-role.json"
    assert main([str(valid)]) == 0
    assert "ok" in capsys.readouterr().out

    assert main([str(valid), str(invalid)]) == 1
    captured = capsys.readouterr()
    assert "$.events[0].role" in captured.err
    assert "narrator" not in captured.err  # content is never echoed

    broken = tmp_path / "broken.json"
    broken.write_text("{not json")
    assert main([str(broken)]) == 2
    assert main([str(tmp_path / "missing.json")]) == 2

    out = tmp_path / "converted.json"
    assert main(["--agent-log", str(_AGENT_LOG), "--output", str(out)]) == 0
    assert load_conversation_file(out) == _load("valid/agent-product-log.json")
    assert main(["--normalized", str(valid)]) == 0
    assert '"schema_version": 1' in capsys.readouterr().out
    assert main(["--output", str(out), str(valid), str(invalid)]) == 2
