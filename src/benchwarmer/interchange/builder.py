"""Build a conversation file from Python without hand-assembling dictionaries.

The builder appends events in order (parents must come first), attaches
context items, tool definitions, provenance, and annotations, and renders a
document that ``validate_conversation_file`` accepts. It performs no I/O and
never contacts the library.
"""

from __future__ import annotations

from typing import Any

from benchwarmer.interchange.format import (
    FORMAT,
    FORMAT_VERSION,
    ConversationFileError,
    validate_conversation_file,
)


def _prune(
    mapping: dict[str, Any], *, keep_none: tuple[str, ...] = ()
) -> dict[str, Any]:
    return {k: v for k, v in mapping.items() if v is not None or k in keep_none}


def text_block(text: str) -> dict[str, Any]:
    return {"kind": "text", "text": text}


def reasoning_block(text: str) -> dict[str, Any]:
    return {"kind": "reasoning", "text": text}


def tool_call_block(
    tool_call_id: str, tool_name: str, input: Any = None, *, text: str | None = None
) -> dict[str, Any]:
    call: dict[str, Any] = {
        "kind": "tool_call",
        "tool_call_id": tool_call_id,
        "tool_name": tool_name,
    }
    if input is not None:
        call["input"] = input
    if text is not None:
        call["text"] = text
    return call


def tool_result_block(
    tool_call_id: str,
    output: Any = None,
    *,
    is_error: bool | None = None,
    text: str | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {"kind": "tool_result", "tool_call_id": tool_call_id}
    if output is not None:
        result["output"] = output
    if is_error is not None:
        result["is_error"] = is_error
    if text is not None:
        result["text"] = text
    return result


def attachment_block(context_id: str, *, text: str | None = None) -> dict[str, Any]:
    return _prune({"kind": "attachment", "context_id": context_id, "text": text})


def provenance(
    model: str,
    *,
    provider: str | None = None,
    params: dict[str, Any] | None = None,
    system_prompt_sha256: str | None = None,
    usage: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Per-turn model provenance for an assistant event."""
    return _prune(
        {
            "model": model,
            "provider": provider,
            "params": params,
            "system_prompt_sha256": system_prompt_sha256,
            "usage": usage,
        }
    )


class ConversationFileBuilder:
    """Accumulate one conversation and render it as a format v1 document."""

    def __init__(
        self,
        *,
        scope_id: str,
        native_id: str,
        source_version: str | None = None,
        title: str | None = None,
    ) -> None:
        self.scope_id = scope_id
        self.native_id = native_id
        self.source_version = source_version
        self.title = title
        self.events: list[dict[str, Any]] = []
        self.tools: list[dict[str, Any]] = []
        self.context: list[dict[str, Any]] = []
        self.annotations: list[dict[str, Any]] = []
        self.relationships: list[dict[str, Any]] = []
        self.metadata: list[dict[str, Any]] = []
        self.coverage: dict[str, str] | None = None
        self.extensions: dict[str, Any] = {}
        self.native: Any = None

    def add_event(
        self,
        native_id: str,
        role: str,
        content: list[dict[str, Any]],
        *,
        parent_native_id: str | None = None,
        kind: str = "message",
        occurred_at: str | None = None,
        provenance: dict[str, Any] | None = None,
        supersedes_native_id: str | None = None,
        extensions: dict[str, Any] | None = None,
    ) -> str:
        """Append one event and return its native id for chaining as a parent."""
        self.events.append(
            _prune(
                {
                    "native_id": native_id,
                    "parent_native_id": parent_native_id,
                    "kind": kind,
                    "role": role,
                    "occurred_at": occurred_at,
                    "content": list(content),
                    "provenance": provenance,
                    "supersedes_native_id": supersedes_native_id,
                    "extensions": extensions,
                },
                keep_none=("parent_native_id",),
            )
        )
        return native_id

    def add_system_prompt(
        self,
        native_id: str,
        text: str,
        *,
        parent_native_id: str | None = None,
        occurred_at: str | None = None,
    ) -> str:
        """A configuration event carrying the system prompt text."""
        return self.add_event(
            native_id,
            "system",
            [text_block(text)],
            parent_native_id=parent_native_id,
            kind="configuration",
            occurred_at=occurred_at,
        )

    def add_tool(
        self,
        name: str,
        *,
        description: str | None = None,
        input_schema: dict[str, Any] | None = None,
    ) -> None:
        self.tools.append(
            _prune(
                {"name": name, "description": description, "input_schema": input_schema}
            )
        )

    def add_context(
        self,
        context_id: str,
        *,
        kind: str | None = None,
        name: str | None = None,
        media_type: str | None = None,
        text: str | None = None,
    ) -> str:
        """Register an attached context item; reference it with ``attachment_block``."""
        self.context.append(
            _prune(
                {
                    "id": context_id,
                    "kind": kind,
                    "name": name,
                    "media_type": media_type,
                    "text": text,
                }
            )
        )
        return context_id

    def add_feedback(
        self,
        *,
        event_native_id: str | None,
        rating: str | int | None = None,
        text: str | None = None,
        by: str | None = None,
        at: str | None = None,
    ) -> None:
        """Human feedback on one event, kept as an annotation of human origin."""
        self.add_annotation(
            "feedback",
            event_native_id=event_native_id,
            rating=rating,
            text=text,
            by=by,
            at=at,
        )

    def add_annotation(
        self,
        kind: str,
        *,
        event_native_id: str | None = None,
        rating: str | int | None = None,
        text: str | None = None,
        by: str | None = None,
        at: str | None = None,
    ) -> None:
        self.annotations.append(
            _prune(
                {
                    "kind": kind,
                    "event_native_id": event_native_id,
                    "rating": rating,
                    "text": text,
                    "by": by,
                    "at": at,
                }
            )
        )

    def add_relationship(
        self,
        kind: str,
        *,
        target_scope_id: str,
        target_native_id: str,
        target_source_kind: str | None = None,
    ) -> None:
        self.relationships.append(
            _prune(
                {
                    "kind": kind,
                    "target_scope_id": target_scope_id,
                    "target_native_id": target_native_id,
                    "target_source_kind": target_source_kind,
                }
            )
        )

    def add_metadata(self, name: str, value: Any) -> None:
        self.metadata.append({"name": name, "value": value})

    def build(self, *, validate: bool = True) -> dict[str, Any]:
        """Render the document; with ``validate`` it must pass the full validator."""
        document: dict[str, Any] = {
            "format": FORMAT,
            "format_version": FORMAT_VERSION,
            "scope_id": self.scope_id,
            "native_id": self.native_id,
            "events": [dict(item) for item in self.events],
        }
        if self.source_version is not None:
            document["source_version"] = self.source_version
        if self.title is not None:
            document["title"] = self.title
        for key in ("tools", "context", "annotations", "relationships", "metadata"):
            values = getattr(self, key)
            if values:
                document[key] = [dict(item) for item in values]
        if self.coverage is not None:
            document["coverage"] = dict(self.coverage)
        if self.extensions:
            document["extensions"] = dict(self.extensions)
        if self.native is not None:
            document["native"] = self.native
        if validate:
            issues = validate_conversation_file(document)
            if issues:
                raise ConversationFileError(issues)
        return document
