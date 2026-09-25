"""Read an explicitly supplied ChatGPT account export, never the macOS cache."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
import re
from typing import Any
import zipfile

from sqlalchemy.orm import Session

from benchwarmer.adapters.file_conversations import (
    FileConversation,
    FileConversationError,
    FileImportResult,
    block,
    event,
    import_file_conversations,
)
from benchwarmer.config import BenchwarmerSettings

ADAPTER_VERSION = "1"
_MAX_EXPORT_BYTES = 512 * 1024 * 1024
_CONVERSATION_NAME = re.compile(r"conversations(?:[-_][0-9]+)?\.json")


def _conversation_files(path: Path) -> list[bytes]:
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise FileConversationError("ChatGPT export path is unusable")
    if path.suffix.lower() == ".zip":
        try:
            with zipfile.ZipFile(path) as archive:
                names = [
                    name
                    for name in archive.namelist()
                    if _CONVERSATION_NAME.fullmatch(Path(name).name)
                ]
                if (
                    not names
                    or sum(archive.getinfo(name).file_size for name in names)
                    > _MAX_EXPORT_BYTES
                ):
                    raise FileConversationError(
                        "ChatGPT export has no supported conversation files"
                    )
                return [archive.read(name) for name in sorted(names)]
        except (OSError, zipfile.BadZipFile, RuntimeError) as error:
            raise FileConversationError("ChatGPT export could not be read") from error
    if _CONVERSATION_NAME.fullmatch(path.name):
        try:
            if path.stat().st_size > _MAX_EXPORT_BYTES:
                raise FileConversationError("ChatGPT export is too large")
            return [path.read_bytes()]
        except OSError as error:
            raise FileConversationError("ChatGPT export could not be read") from error
    raise FileConversationError("ChatGPT export format is unsupported")


def _timestamp(value: object) -> str | None:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    try:
        return dt.datetime.fromtimestamp(value, dt.UTC).isoformat()
    except (ValueError, OverflowError, OSError):
        return None


def _ordered_nodes(mapping: dict[str, Any]) -> list[str]:
    ordered: list[str] = []
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node_id: str) -> None:
        if node_id in visiting:
            raise FileConversationError("ChatGPT export contains a node cycle")
        if node_id in visited:
            return
        node = mapping[node_id]
        if not isinstance(node, dict):
            raise FileConversationError("ChatGPT export node is invalid")
        visiting.add(node_id)
        parent = node.get("parent")
        if parent is not None:
            if not isinstance(parent, str) or parent not in mapping:
                raise FileConversationError("ChatGPT export node parent is invalid")
            visit(parent)
        visiting.remove(node_id)
        visited.add(node_id)
        ordered.append(node_id)

    for key in mapping:
        visit(key)
    return ordered


def _parse_conversation(raw: object) -> FileConversation:
    if not isinstance(raw, dict) or not isinstance(raw.get("id"), str) or not raw["id"]:
        raise FileConversationError("ChatGPT export conversation identity is invalid")
    mapping = raw.get("mapping")
    if (
        not isinstance(mapping, dict)
        or not mapping
        or any(not isinstance(key, str) or not key for key in mapping)
    ):
        raise FileConversationError("ChatGPT export mapping is unsupported")
    normalized: list[dict[str, object]] = []
    unsupported_content = False
    for index, node_id in enumerate(_ordered_nodes(mapping), start=1):
        node = mapping[node_id]
        message = node.get("message")
        role = "unknown"
        parts: list[dict[str, object]] = []
        time = None
        if isinstance(message, dict):
            author = message.get("author")
            if isinstance(author, dict) and author.get("role") in {
                "system",
                "developer",
                "user",
                "assistant",
                "tool",
            }:
                role = author["role"]
            time = _timestamp(message.get("create_time"))
            content = message.get("content")
            if (
                isinstance(content, dict)
                and content.get("content_type") == "text"
                and isinstance(content.get("parts"), list)
            ):
                for value in content["parts"]:
                    if isinstance(value, str):
                        parts.append(block(node_id, len(parts), "text", value))
                    else:
                        unsupported_content = True
            elif content is not None:
                unsupported_content = True
        normalized.append(
            event(
                node_id,
                index * 10,
                node.get("parent"),
                "message" if isinstance(message, dict) else "unknown",
                role,
                time,
                parts,
                {"chatgpt_node_without_message": message is None},
            )
        )
    metadata: list[tuple[str, object]] = []
    if isinstance(raw.get("title"), str):
        metadata.append(("title", raw["title"]))
    if isinstance(raw.get("current_node"), str):
        metadata.append(("current_node", raw["current_node"]))
    return FileConversation(
        raw["id"],
        raw,
        tuple(normalized),
        metadata=tuple(metadata),
        coverage={
            "messages": "partial" if unsupported_content else "available",
            "branches": "available",
            "usage": "unknown",
            "prompts": "unknown",
            "tool_calls": "partial",
        },
    )


def read_chatgpt_export(path: Path) -> tuple[FileConversation, ...]:
    """Parse supported conversation JSON from a user-requested account export."""
    conversations: list[FileConversation] = []
    seen: set[str] = set()
    for payload in _conversation_files(path):
        try:
            items = json.loads(payload)
        except (UnicodeDecodeError, ValueError) as error:
            raise FileConversationError("ChatGPT export JSON is invalid") from error
        if not isinstance(items, list):
            raise FileConversationError("ChatGPT export shape is unsupported")
        for raw in items:
            item = _parse_conversation(raw)
            if item.native_id in seen:
                raise FileConversationError(
                    "ChatGPT export contains duplicate conversations"
                )
            seen.add(item.native_id)
            conversations.append(item)
    return tuple(conversations)


def import_chatgpt_export(
    settings: BenchwarmerSettings,
    session: Session,
    *,
    source_id: str,
    path: Path,
    batch_id: str,
    idempotency_key: str,
) -> FileImportResult:
    """Import an explicit ChatGPT export; no macOS cache or account API access."""
    items = read_chatgpt_export(path)
    return import_file_conversations(
        settings,
        session,
        source_id=source_id,
        source_kind="chatgpt",
        batch_id=batch_id,
        idempotency_key=idempotency_key,
        items=items,
        adapter_version=ADAPTER_VERSION,
        source_version="account-export",
    )
