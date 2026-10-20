"""Import deliberately synthetic conversation fixtures through the file importer."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
import datetime as dt
import json
from pathlib import Path
import sys
from typing import Any

from benchwarmer.adapters.file_conversations import (
    FileConversation,
    FileConversationError,
    import_file_conversations,
)
from benchwarmer.config import BenchwarmerSettings
from benchwarmer.db import create_engine, create_session_factory

_MAX_FIXTURE_BYTES = 1_048_576


class DemoConversationError(ValueError):
    """Raised when a synthetic conversation fixture cannot be loaded."""


def _conversation(entry: dict[str, Any]) -> FileConversation:
    metadata: list[tuple[str, object]] = []
    if entry.get("title"):
        metadata.append(("title", entry["title"]))
    if entry.get("usage"):
        metadata.append(("usage_observations", entry["usage"]))
    return FileConversation(
        native_id=entry["native_id"],
        native={"id": entry["native_id"], "synthetic": True},
        events=tuple(entry["events"]),
        relationships=tuple(entry.get("relationships", ())),
        metadata=tuple(metadata),
        coverage=entry.get("coverage"),
    )


def load_demo_conversations(settings: BenchwarmerSettings, path: Path) -> int:
    """Import every batch in a fixture; return the number of new revisions."""
    if path.stat().st_size > _MAX_FIXTURE_BYTES:
        raise DemoConversationError("fixture is too large")
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("schema_version") != 1:
        raise DemoConversationError("unsupported fixture schema version")
    engine = create_engine(settings)
    factory = create_session_factory(engine)
    revisions = 0
    try:
        for batch in document["imports"]:
            with factory() as session:
                result = import_file_conversations(
                    settings,
                    session,
                    source_id=batch["source_id"],
                    source_kind=batch["source_kind"],
                    batch_id=batch["batch_id"],
                    idempotency_key=batch["batch_id"],
                    items=tuple(_conversation(item) for item in batch["conversations"]),
                    adapter_version="synthetic-fixture-1",
                    captured_at=dt.datetime.fromisoformat(batch["captured_at"]),
                )
                revisions += result.revisions
    except (FileConversationError, KeyError, TypeError) as error:
        raise DemoConversationError(f"fixture could not be imported: {error}") from None
    finally:
        engine.dispose()
    return revisions


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--load",
        type=Path,
        required=True,
        metavar="PATH",
        help="load a synthetic conversation fixture",
    )
    return parser


def main(arguments: Sequence[str] | None = None) -> int:
    """Load one fixture using the configured private data root."""
    options = _parser().parse_args(arguments)
    try:
        revisions = load_demo_conversations(
            BenchwarmerSettings.from_environment(), options.load
        )
    except DemoConversationError as error:
        print(str(error), file=sys.stderr)
        return 1
    print(f"loaded conversation revisions={revisions}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
