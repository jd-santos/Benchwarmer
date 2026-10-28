"""Reference converter: a synthetic agent product log to a conversation file.

The input shape is invented for documentation and tests; it stands in for the
kind of per-conversation log an agent product writes. Its fields and the
mapping are described in ``docs/conversation-interchange.md``. Nothing here is
specific to a real product.

Log shape (``example-agent-log`` version 1)::

    {
      "log_format": "example-agent-log",
      "log_version": 1,
      "tenant": "tenant-a",
      "conversation_id": "conv-001",
      "app_version": "2.3.0",
      "title": "optional",
      "system_prompt": "optional text",
      "tools": [{"name": "...", "description": "...", "parameters": {...}}],
      "attachments": [{"id": "att-1", "name": "...", "mime_type": "...", "content": "..."}],
      "turns": [
        {"id": "t1", "role": "user", "created_at": "...", "text": "...",
         "attachment_ids": ["att-1"]},
        {"id": "t2", "role": "assistant", "created_at": "...",
         "blocks": [{"type": "text", "text": "..."},
                    {"type": "thinking", "text": "..."},
                    {"type": "tool_use", "id": "call-1", "name": "...", "input": {...}}],
         "model_call": {"model": "...", "provider": "...", "parameters": {...},
                        "usage": {...}, "raw_response": {...}}},
        {"id": "t3", "role": "tool", "created_at": "...", "tool_use_id": "call-1",
         "output": {...}, "is_error": false},
        {"id": "t5", "role": "user", "text": "...", "rewind_to": "t1"}
      ],
      "feedback": [{"turn_id": "t2", "rating": "down", "comment": "...",
                    "user": "...", "created_at": "..."}]
    }

A turn's parent is the previous turn unless ``rewind_to`` names an earlier
turn, in which case the new turn branches from that turn and supersedes the
turn that previously followed it.
"""

from __future__ import annotations

import hashlib
from typing import Any

from benchwarmer.interchange.builder import (
    ConversationFileBuilder,
    attachment_block,
    provenance,
    reasoning_block,
    text_block,
    tool_call_block,
    tool_result_block,
)

LOG_FORMAT = "example-agent-log"
LOG_VERSION = 1


class AgentLogError(ValueError):
    """The agent log is missing a field the converter needs."""


def _require(mapping: dict[str, Any], key: str, where: str) -> Any:
    if key not in mapping:
        raise AgentLogError(f"{where} lacks {key!r}")
    return mapping[key]


def convert_agent_log(log: dict[str, Any]) -> dict[str, Any]:
    """Convert one agent log to a validated conversation file document."""
    if log.get("log_format") != LOG_FORMAT or log.get("log_version") != LOG_VERSION:
        raise AgentLogError(f"expected log_format {LOG_FORMAT!r} version {LOG_VERSION}")
    builder = ConversationFileBuilder(
        scope_id=str(_require(log, "tenant", "log")),
        native_id=str(_require(log, "conversation_id", "log")),
        source_version=f"{LOG_FORMAT}-{LOG_VERSION}"
        + (f"/{log['app_version']}" if log.get("app_version") else ""),
        title=log.get("title"),
    )
    for tool in log.get("tools") or []:
        builder.add_tool(
            str(_require(tool, "name", "tool")),
            description=tool.get("description"),
            input_schema=tool.get("parameters"),
        )
    for attachment in log.get("attachments") or []:
        builder.add_context(
            str(_require(attachment, "id", "attachment")),
            kind="attachment",
            name=attachment.get("name"),
            media_type=attachment.get("mime_type"),
            text=attachment.get("content"),
        )

    system_prompt = log.get("system_prompt")
    prompt_digest = None
    previous: str | None = None
    if isinstance(system_prompt, str):
        prompt_digest = hashlib.sha256(system_prompt.encode("utf-8")).hexdigest()
        previous = builder.add_system_prompt("system-prompt", system_prompt)

    first_child: dict[str, str] = {}
    calls: set[str] = set()
    results: set[str] = set()
    raw_responses: list[dict[str, Any]] = []
    has_usage = False
    for turn in _require(log, "turns", "log"):
        turn_id = str(_require(turn, "id", "turn"))
        role = _require(turn, "role", f"turn {turn_id}")
        rewind_to = turn.get("rewind_to")
        parent = str(rewind_to) if rewind_to is not None else previous
        supersedes = first_child.get(parent) if rewind_to is not None else None
        content: list[dict[str, Any]] = []
        turn_provenance = None
        if role == "user":
            if isinstance(turn.get("text"), str):
                content.append(text_block(turn["text"]))
            for attachment_id in turn.get("attachment_ids") or []:
                content.append(attachment_block(str(attachment_id)))
        elif role == "assistant":
            for part in turn.get("blocks") or []:
                kind = part.get("type")
                if kind == "text" and isinstance(part.get("text"), str):
                    content.append(text_block(part["text"]))
                elif kind == "thinking" and isinstance(part.get("text"), str):
                    content.append(reasoning_block(part["text"]))
                elif kind == "tool_use":
                    call_id = str(_require(part, "id", f"tool_use in turn {turn_id}"))
                    calls.add(call_id)
                    content.append(
                        tool_call_block(
                            call_id,
                            str(_require(part, "name", f"tool_use {call_id}")),
                            part.get("input"),
                        )
                    )
                else:
                    content.append({"kind": "unknown", "text": None})
            model_call = turn.get("model_call")
            if isinstance(model_call, dict):
                usage = model_call.get("usage")
                has_usage = has_usage or usage is not None
                turn_provenance = provenance(
                    str(_require(model_call, "model", f"model_call in turn {turn_id}")),
                    provider=model_call.get("provider"),
                    params=model_call.get("parameters"),
                    system_prompt_sha256=prompt_digest,
                    usage=usage,
                )
                if "raw_response" in model_call:
                    raw_responses.append(
                        {"turn_id": turn_id, "response": model_call["raw_response"]}
                    )
        elif role == "tool":
            call_id = str(_require(turn, "tool_use_id", f"tool turn {turn_id}"))
            results.add(call_id)
            content.append(
                tool_result_block(
                    call_id, turn.get("output"), is_error=turn.get("is_error")
                )
            )
            role = "tool"
        else:
            role = "unknown"
        builder.add_event(
            turn_id,
            role,
            content,
            parent_native_id=parent,
            occurred_at=turn.get("created_at"),
            provenance=turn_provenance,
            supersedes_native_id=supersedes,
        )
        if parent is not None and parent not in first_child:
            first_child[parent] = turn_id
        previous = turn_id

    for item in log.get("feedback") or []:
        builder.add_feedback(
            event_native_id=str(item["turn_id"]) if item.get("turn_id") else None,
            rating=item.get("rating"),
            text=item.get("comment"),
            by=item.get("user"),
            at=item.get("created_at"),
        )
    builder.coverage = {
        "messages": "available",
        "branches": "available",
        "usage": "partial" if has_usage else "unknown",
        "prompts": "available" if prompt_digest else "unavailable",
        "tool_calls": "available" if calls <= results else "partial",
    }
    if raw_responses:
        builder.native = {"raw_responses": raw_responses}
    return builder.build()
