import datetime as dt

import pytest
from sqlalchemy.exc import IntegrityError

from benchwarmer.models.import_batch import (
    ImportBatch,
    ImportCoverage,
    ImportCursor,
)
from benchwarmer.models.source import Source


def _source() -> Source:
    return Source(
        id="source-opaque-1",
        kind="hermes",
        scope_id="scope-opaque-1",
        display_name="Configured Hermes",
    )


def test_import_batches_preserve_each_terminal_attempt(session) -> None:
    source = _source()
    session.add(source)
    session.commit()
    started = dt.datetime(2026, 9, 16, 14, 0, tzinfo=dt.UTC)

    batches = [
        ImportBatch(
            id="batch-failed",
            source_id=source.id,
            idempotency_key="attempt-1",
            outcome="failed",
            cursor_before=ImportCursor("message-10"),
            started_at=started,
            completed_at=started + dt.timedelta(seconds=2),
            error_summary="source database was unavailable",
        ),
        ImportBatch(
            id="batch-partial",
            source_id=source.id,
            idempotency_key="attempt-2",
            outcome="partial",
            cursor_before=ImportCursor("message-10"),
            cursor_after=ImportCursor({"message_id": "message-14"}),
            observed_coverage=ImportCoverage(
                {"messages": "available", "usage": "partial"}
            ),
            started_at=started + dt.timedelta(minutes=1),
            completed_at=started + dt.timedelta(minutes=1, seconds=5),
            error_summary="one attachment could not be read",
        ),
        ImportBatch(
            id="batch-succeeded",
            source_id=source.id,
            idempotency_key="attempt-3",
            outcome="succeeded",
            cursor_before=ImportCursor({"message_id": "message-14"}),
            cursor_after=ImportCursor({"message_id": "message-20"}),
            observed_coverage=ImportCoverage(
                {"messages": "available", "reasoning": "redacted"}
            ),
            started_at=started + dt.timedelta(minutes=2),
            completed_at=started + dt.timedelta(minutes=2, seconds=3),
        ),
    ]
    batch_ids = [batch.id for batch in batches]
    session.add_all(batches)
    session.commit()
    session.expunge_all()

    restored = [session.get(ImportBatch, batch_id) for batch_id in batch_ids]

    assert [batch.outcome for batch in restored if batch is not None] == [
        "failed",
        "partial",
        "succeeded",
    ]
    assert restored[1] is not None
    assert restored[1].cursor_after == ImportCursor({"message_id": "message-14"})
    assert restored[1].observed_coverage == ImportCoverage(
        {"messages": "available", "usage": "partial"}
    )
    assert restored[1].started_at.tzinfo is dt.UTC
    assert restored[1].completed_at.tzinfo is dt.UTC


def test_import_batch_idempotency_key_is_unique_per_source(session) -> None:
    first_source = _source()
    second_source = Source(
        id="source-opaque-2",
        kind="pi",
        scope_id="scope-opaque-2",
        display_name="Configured Pi",
    )
    session.add_all([first_source, second_source])
    session.commit()

    def batch(batch_id: str, source_id: str) -> ImportBatch:
        return ImportBatch(
            id=batch_id,
            source_id=source_id,
            idempotency_key="same-request",
            outcome="succeeded",
        )

    session.add(batch("batch-one", first_source.id))
    session.commit()
    session.add(batch("batch-two", first_source.id))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()

    session.add(batch("batch-three", second_source.id))
    session.commit()


def test_import_batch_requires_existing_source(session) -> None:
    session.add(
        ImportBatch(
            id="batch-orphan",
            source_id="missing-source",
            idempotency_key="attempt-1",
            outcome="succeeded",
        )
    )

    with pytest.raises(IntegrityError):
        session.commit()


@pytest.mark.parametrize("value", ["", "running", "success", "FAILED"])
def test_import_batch_rejects_invalid_outcome(value: str) -> None:
    with pytest.raises(ValueError, match="outcome"):
        ImportBatch(
            id="batch-one",
            source_id="source-one",
            idempotency_key="attempt-1",
            outcome=value,
        )


def test_import_batch_rejects_naive_or_reversed_timestamps(session) -> None:
    with pytest.raises(ValueError, match="UTC-aware"):
        ImportBatch(
            id="batch-one",
            source_id="source-one",
            idempotency_key="attempt-1",
            outcome="succeeded",
            started_at=dt.datetime(2026, 9, 16, 14, 0),
        )

    source = _source()
    session.add(source)
    session.add(
        ImportBatch(
            id="batch-two",
            source_id=source.id,
            idempotency_key="attempt-2",
            outcome="succeeded",
            started_at=dt.datetime(2026, 9, 16, 14, 1, tzinfo=dt.UTC),
            completed_at=dt.datetime(2026, 9, 16, 14, 0, tzinfo=dt.UTC),
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()


def test_import_metadata_is_versioned_immutable_and_validated() -> None:
    cursor = ImportCursor({"page": 2, "keys": ["a", "b"]})
    value = cursor.value
    value["page"] = 99

    assert cursor.value == {"page": 2, "keys": ["a", "b"]}
    assert ImportCursor.from_mapping(cursor.to_storage()) == cursor

    coverage = ImportCoverage({"messages": "available", "tools": "unknown"})
    with pytest.raises(TypeError):
        coverage.dimensions["tools"] = "available"  # type: ignore[index]

    with pytest.raises(ValueError, match="cursor"):
        ImportCursor.from_mapping({"schema_version": 2, "value": "cursor"})
    with pytest.raises(ValueError, match="coverage"):
        ImportCoverage({"messages": "unsupported"})


def test_import_batch_requires_error_summary_for_failure(session) -> None:
    source = _source()
    session.add(source)
    session.add(
        ImportBatch(
            id="batch-failed",
            source_id=source.id,
            idempotency_key="attempt-1",
            outcome="failed",
        )
    )

    with pytest.raises(IntegrityError):
        session.commit()
