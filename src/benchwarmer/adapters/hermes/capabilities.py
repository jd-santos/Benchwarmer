"""Versioned, read-only capability definitions for Hermes SQLite stores."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

ADAPTER_VERSION = "1"
CAPABILITY_MANIFEST_VERSION = 1
SCHEMA_VERSION = 30


class HermesCapabilityError(ValueError):
    """Raised when a Hermes store cannot satisfy the supported manifest.

    Messages name only schema capabilities and never source paths or row values.
    """


@dataclass(frozen=True, slots=True)
class TableCapability:
    """The required and optional shape of one source-native table."""

    name: str
    required_columns: frozenset[str]
    optional_columns: frozenset[str]
    primary_key: tuple[str, ...]
    foreign_keys: Mapping[str, tuple[str, str]]
    required: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "foreign_keys", MappingProxyType(dict(self.foreign_keys))
        )


# Identity, lineage, timestamps, message payload, and usage provenance must be
# present before a later importer can safely normalize a source-native snapshot.
_SESSION_REQUIRED = frozenset(
    {
        "id",
        "source",
        "model",
        "model_config",
        "system_prompt",
        "system_prompt_hash",
        "parent_session_id",
        "started_at",
        "ended_at",
        "end_reason",
        "input_tokens",
        "output_tokens",
        "cache_read_tokens",
        "cache_write_tokens",
        "reasoning_tokens",
        "billing_provider",
        "billing_base_url",
        "billing_mode",
        "estimated_cost_usd",
        "actual_cost_usd",
        "cost_status",
        "cost_source",
        "pricing_version",
        "title",
        "archived",
        "pinned",
    }
)
_SESSION_OPTIONAL = frozenset(
    {
        "user_id",
        "session_key",
        "chat_id",
        "chat_type",
        "thread_id",
        "display_name",
        "origin_json",
        "expiry_finalized",
        "message_count",
        "tool_call_count",
        "cwd",
        "git_branch",
        "git_repo_root",
        "git_metadata_generation",
        "title_source",
        "last_activity_at",
        "last_activity_description",
        "last_activity_provenance",
        "api_call_count",
        "handoff_state",
        "handoff_platform",
        "handoff_error",
        "compression_failure_cooldown_until",
        "compression_failure_error",
        "compression_fallback_streak",
        "compression_ineffective_count",
        "compression_recovery_deadline",
        "profile_name",
        "rewind_count",
        "hidden",
        "last_read_at",
        "tool_names",
    }
)
_MESSAGE_REQUIRED = frozenset(
    {
        "id",
        "session_id",
        "role",
        "content",
        "tool_call_id",
        "tool_calls",
        "tool_name",
        "effect_disposition",
        "timestamp",
        "token_count",
        "finish_reason",
        "reasoning",
        "reasoning_content",
        "reasoning_details",
        "codex_reasoning_items",
        "codex_message_items",
        "platform_message_id",
        "observed",
        "_compressed_summary",
        "active",
        "compacted",
    }
)
_MESSAGE_OPTIONAL = frozenset({"api_content", "display_kind", "display_metadata"})
_USAGE_REQUIRED = frozenset(
    {
        "session_id",
        "model",
        "billing_provider",
        "billing_base_url",
        "billing_mode",
        "task",
        "api_call_count",
        "input_tokens",
        "output_tokens",
        "cache_read_tokens",
        "cache_write_tokens",
        "reasoning_tokens",
        "estimated_cost_usd",
        "actual_cost_usd",
        "cost_status",
        "cost_source",
        "first_seen",
        "last_seen",
    }
)

SCHEMA_30_TABLES: tuple[TableCapability, ...] = (
    TableCapability(
        "system_prompts", frozenset({"hash", "prompt"}), frozenset(), ("hash",), {}
    ),
    TableCapability(
        "sessions",
        _SESSION_REQUIRED,
        _SESSION_OPTIONAL,
        ("id",),
        {
            "parent_session_id": ("sessions", "id"),
            "system_prompt_hash": ("system_prompts", "hash"),
        },
    ),
    TableCapability(
        "messages",
        _MESSAGE_REQUIRED,
        _MESSAGE_OPTIONAL,
        ("id",),
        {"session_id": ("sessions", "id")},
    ),
    TableCapability(
        "session_model_usage",
        _USAGE_REQUIRED,
        frozenset(),
        (
            "session_id",
            "model",
            "billing_provider",
            "billing_base_url",
            "billing_mode",
            "task",
        ),
        {"session_id": ("sessions", "id")},
    ),
    # Gateway routing is not normalized in the first importer, but an existing
    # table must still expose its canonical payload rather than silently losing it.
    TableCapability(
        "gateway_routing",
        frozenset({"scope", "session_key", "entry_json", "updated_at"}),
        frozenset(),
        ("scope", "session_key"),
        {},
        required=False,
    ),
)
SCHEMA_30_MANIFEST = MappingProxyType({table.name: table for table in SCHEMA_30_TABLES})


def manifest_for_schema(schema_version: int) -> Mapping[str, TableCapability]:
    """Return the supported manifest or fail closed for another schema."""
    if schema_version != SCHEMA_VERSION:
        raise HermesCapabilityError(
            f"unsupported Hermes schema version: {schema_version}"
        )
    return SCHEMA_30_MANIFEST
