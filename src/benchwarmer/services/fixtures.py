"""Load deliberately synthetic source-status fixtures into migrated state."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import datetime as dt
import json
from pathlib import Path
import sys
from typing import Any, NoReturn

from sqlalchemy.exc import SQLAlchemyError

from benchwarmer.config import BenchwarmerSettings
from benchwarmer.db import create_engine, create_session_factory
from benchwarmer.models.import_batch import ImportBatch, ImportCoverage, ImportCursor
from benchwarmer.models.source import ConfiguredCoverage, Source

_MAX_FIXTURE_BYTES = 1_048_576
_SOURCE_KEYS = {
    "id",
    "kind",
    "scope_id",
    "display_name",
    "configured_coverage",
}
_BATCH_KEYS = {
    "id",
    "source_id",
    "idempotency_key",
    "outcome",
    "cursor_before",
    "cursor_after",
    "observed_coverage",
    "started_at",
    "completed_at",
    "error_summary",
}


class FixtureLoadError(ValueError):
    """Report a bounded fixture validation or persistence failure."""


@dataclass(frozen=True, slots=True)
class FixtureLoadResult:
    """Count records created and recognized during an idempotent load."""

    sources_created: int
    batches_created: int
    sources_existing: int
    batches_existing: int


def _invalid_document() -> NoReturn:
    raise FixtureLoadError("invalid fixture document")


def _object(value: object, keys: set[str]) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or set(value) != keys:
        _invalid_document()
    if any(not isinstance(key, str) for key in value):
        _invalid_document()
    return value


def _list(value: object) -> Sequence[object]:
    if not isinstance(value, list):
        _invalid_document()
    return value


def _string(value: object) -> str:
    if not isinstance(value, str):
        _invalid_document()
    return value


def _nullable_string(value: object) -> str | None:
    if value is None:
        return None
    return _string(value)


def _timestamp(value: object) -> dt.datetime:
    if not isinstance(value, str) or "T" not in value:
        _invalid_document()
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        _invalid_document()
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        _invalid_document()
    return parsed.astimezone(dt.UTC)


def _optional_cursor(value: object) -> ImportCursor | None:
    if value is None:
        return None
    return ImportCursor.from_mapping(value)


def _optional_import_coverage(value: object) -> ImportCoverage | None:
    if value is None:
        return None
    return ImportCoverage.from_mapping(value)


def _optional_configured_coverage(value: object) -> ConfiguredCoverage | None:
    if value is None:
        return None
    return ConfiguredCoverage.from_mapping(value)


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            _invalid_document()
        result[key] = value
    return result


def _read_document(path: Path) -> Mapping[str, object]:
    try:
        payload = path.read_bytes()
    except OSError as error:
        raise FixtureLoadError("fixture document could not be read") from error
    if len(payload) > _MAX_FIXTURE_BYTES:
        _invalid_document()
    try:
        value = json.loads(
            payload.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys
        )
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as error:
        raise FixtureLoadError("invalid fixture document") from error
    document = _object(value, {"schema_version", "sources", "import_batches"})
    if type(document["schema_version"]) is not int or document["schema_version"] != 1:
        _invalid_document()
    return document


def _parse_source(value: object) -> Source:
    item = _object(value, _SOURCE_KEYS)
    return Source(
        id=_string(item["id"]),
        kind=_string(item["kind"]),
        scope_id=_string(item["scope_id"]),
        display_name=_string(item["display_name"]),
        configured_coverage=_optional_configured_coverage(item["configured_coverage"]),
    )


def _parse_batch(value: object) -> ImportBatch:
    item = _object(value, _BATCH_KEYS)
    return ImportBatch(
        id=_string(item["id"]),
        source_id=_string(item["source_id"]),
        idempotency_key=_string(item["idempotency_key"]),
        outcome=_string(item["outcome"]),
        cursor_before=_optional_cursor(item["cursor_before"]),
        cursor_after=_optional_cursor(item["cursor_after"]),
        observed_coverage=_optional_import_coverage(item["observed_coverage"]),
        started_at=_timestamp(item["started_at"]),
        completed_at=_timestamp(item["completed_at"]),
        error_summary=_nullable_string(item["error_summary"]),
    )


def _parse_fixture(path: Path) -> tuple[tuple[Source, ...], tuple[ImportBatch, ...]]:
    try:
        document = _read_document(path)
        sources = tuple(_parse_source(item) for item in _list(document["sources"]))
        batches = tuple(
            _parse_batch(item) for item in _list(document["import_batches"])
        )
    except FixtureLoadError:
        raise
    except (TypeError, ValueError) as error:
        raise FixtureLoadError("invalid fixture document") from error

    if len({source.id for source in sources}) != len(sources):
        _invalid_document()
    if len({batch.id for batch in batches}) != len(batches):
        _invalid_document()
    return sources, batches


def _source_matches(stored: Source, fixture: Source) -> bool:
    return (
        stored.id == fixture.id
        and stored.kind == fixture.kind
        and stored.scope_id == fixture.scope_id
        and stored.display_name == fixture.display_name
        and stored.configured_coverage == fixture.configured_coverage
    )


def _batch_matches(stored: ImportBatch, fixture: ImportBatch) -> bool:
    return (
        stored.id == fixture.id
        and stored.source_id == fixture.source_id
        and stored.idempotency_key == fixture.idempotency_key
        and stored.outcome == fixture.outcome
        and stored.cursor_before == fixture.cursor_before
        and stored.cursor_after == fixture.cursor_after
        and stored.observed_coverage == fixture.observed_coverage
        and stored.started_at == fixture.started_at
        and stored.completed_at == fixture.completed_at
        and stored.error_summary == fixture.error_summary
    )


def load_fixture(settings: BenchwarmerSettings, path: Path) -> FixtureLoadResult:
    """Insert a validated fixture atomically, treating exact reloads as no-ops."""
    sources, batches = _parse_fixture(path)
    engine = create_engine(settings)
    factory = create_session_factory(engine)
    sources_created = 0
    sources_existing = 0
    batches_created = 0
    batches_existing = 0

    try:
        with factory() as session, session.begin():
            for source in sources:
                stored = session.get(Source, source.id)
                if stored is None:
                    session.add(source)
                    sources_created += 1
                elif _source_matches(stored, source):
                    sources_existing += 1
                else:
                    raise FixtureLoadError("fixture conflicts with stored record")
            session.flush()

            for batch in batches:
                stored = session.get(ImportBatch, batch.id)
                if stored is None:
                    session.add(batch)
                    batches_created += 1
                elif _batch_matches(stored, batch):
                    batches_existing += 1
                else:
                    raise FixtureLoadError("fixture conflicts with stored record")
    except FixtureLoadError:
        raise
    except SQLAlchemyError as error:
        raise FixtureLoadError("fixture records could not be loaded") from error
    finally:
        engine.dispose()

    return FixtureLoadResult(
        sources_created=sources_created,
        batches_created=batches_created,
        sources_existing=sources_existing,
        batches_existing=batches_existing,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--load",
        type=Path,
        required=True,
        metavar="PATH",
        help="load a versioned synthetic source fixture",
    )
    return parser


def main(arguments: Sequence[str] | None = None) -> int:
    """Load one fixture using the configured private data root."""
    options = _parser().parse_args(arguments)
    try:
        result = load_fixture(BenchwarmerSettings.from_environment(), options.load)
    except FixtureLoadError as error:
        print(str(error), file=sys.stderr)
        return 1
    print(
        f"loaded sources={result.sources_created} batches={result.batches_created}; "
        f"existing sources={result.sources_existing} "
        f"batches={result.batches_existing}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
