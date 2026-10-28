"""Benchwarmer conversation file (format v1): validate, build, convert."""

from benchwarmer.interchange.builder import (
    ConversationFileBuilder,
    attachment_block,
    provenance,
    reasoning_block,
    text_block,
    tool_call_block,
    tool_result_block,
)
from benchwarmer.interchange.format import (
    ADAPTER_VERSION,
    FORMAT,
    FORMAT_VERSION,
    SOURCE_KIND,
    ConversationFileError,
    Issue,
    load_conversation_file,
    normalized_preview,
    parse_conversation_file,
    to_file_conversation,
    validate_conversation_file,
    validate_structure,
)

__all__ = [
    "ADAPTER_VERSION",
    "FORMAT",
    "FORMAT_VERSION",
    "SOURCE_KIND",
    "ConversationFileBuilder",
    "ConversationFileError",
    "Issue",
    "attachment_block",
    "load_conversation_file",
    "normalized_preview",
    "parse_conversation_file",
    "provenance",
    "reasoning_block",
    "text_block",
    "to_file_conversation",
    "tool_call_block",
    "tool_result_block",
    "validate_conversation_file",
    "validate_structure",
]
