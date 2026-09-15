import datetime as dt

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from benchwarmer.models.source import ConfiguredCoverage, Source, utc_now


def test_source_persists_caller_supplied_identity_and_custom_coverage(session) -> None:
    coverage = ConfiguredCoverage.from_mapping(
        {
            "schema_version": 1,
            "dimensions": {
                "sessions": "available",
                "adapter_feature": "partial",
            },
        }
    )
    source = Source(
        id="source-opaque-1",
        kind="hermes",
        scope_id="scope-opaque-1",
        display_name="Configured Hermes",
        configured_coverage=coverage,
    )
    session.add(source)
    session.commit()
    session.expunge_all()

    restored = session.get(Source, "source-opaque-1")

    assert restored is not None
    assert restored.id == "source-opaque-1"
    assert restored.scope_id == "scope-opaque-1"
    assert restored.configured_coverage == coverage
    assert restored.configured_coverage is not None
    assert restored.configured_coverage.dimensions["adapter_feature"] == "partial"
    assert restored.created_at.tzinfo is dt.UTC
    assert restored.updated_at.tzinfo is dt.UTC


def test_source_allows_null_configured_coverage(session) -> None:
    source = Source(
        id="source-opaque-1",
        kind="pi",
        scope_id="scope-opaque-1",
        display_name="Configured Pi",
    )
    session.add(source)
    session.commit()

    assert session.get(Source, source.id).configured_coverage is None
    assert session.scalar(
        select(Source.id).where(Source.configured_coverage.is_(None))
    ) == (source.id)


@pytest.mark.parametrize(
    "value",
    [
        {},
        {"schema_version": 2, "dimensions": {}},
        {"schema_version": True, "dimensions": {}},
        {"schema_version": 1.0, "dimensions": {}},
        {"schema_version": 1, "dimensions": {"": "available"}},
        {"schema_version": 1, "dimensions": {"sessions": "redacted"}},
        {"schema_version": 1, "dimensions": {"sessions": "available"}, "extra": 1},
    ],
)
def test_configured_coverage_rejects_invalid_shape_or_state(value: object) -> None:
    with pytest.raises(ValueError, match="configured coverage"):
        ConfiguredCoverage.from_mapping(value)


def test_configured_coverage_rejects_unbounded_dimensions_and_names() -> None:
    with pytest.raises(ValueError, match="configured coverage"):
        ConfiguredCoverage.from_mapping(
            {"schema_version": 1, "dimensions": {"x" * 129: "available"}}
        )

    with pytest.raises(ValueError, match="configured coverage"):
        ConfiguredCoverage.from_mapping(
            {
                "schema_version": 1,
                "dimensions": {
                    f"dimension-{index}": "available" for index in range(65)
                },
            }
        )


def test_configured_coverage_is_immutable_and_validated_on_construction() -> None:
    coverage = ConfiguredCoverage.from_mapping(
        {"schema_version": 1, "dimensions": {"sessions": "available"}}
    )

    with pytest.raises(TypeError):
        coverage.dimensions["sessions"] = "unknown"  # type: ignore[index]

    with pytest.raises(ValueError, match="configured coverage"):
        ConfiguredCoverage({"sessions": "redacted"})


def test_source_normalizes_aware_timestamps_to_utc_and_rejects_naive_values(
    session,
) -> None:
    offset_time = dt.datetime(
        2026, 9, 15, 9, 0, tzinfo=dt.timezone(dt.timedelta(hours=-5))
    )
    source = Source(
        id="source-opaque-1",
        kind="codex",
        scope_id="scope-opaque-1",
        display_name="Configured Codex",
        created_at=offset_time,
        updated_at=offset_time,
    )
    session.add(source)
    session.commit()
    source_id = source.id
    session.expunge_all()

    restored = session.get(Source, source_id)
    assert restored is not None
    assert restored.created_at == dt.datetime(2026, 9, 15, 14, 0, tzinfo=dt.UTC)
    assert restored.updated_at == dt.datetime(2026, 9, 15, 14, 0, tzinfo=dt.UTC)

    with pytest.raises(ValueError, match="UTC-aware"):
        Source(
            id="source-opaque-2",
            kind="codex",
            scope_id="scope-opaque-2",
            display_name="Naive source",
            created_at=dt.datetime(2026, 9, 15, 14, 0),
        )


def test_source_update_advances_updated_at_without_changing_created_at(session) -> None:
    source = Source(
        id="source-opaque-1",
        kind="hermes",
        scope_id="scope-opaque-1",
        display_name="Before update",
        created_at=dt.datetime(2026, 9, 15, 14, 0, tzinfo=dt.UTC),
        updated_at=dt.datetime(2026, 9, 15, 14, 0, tzinfo=dt.UTC),
    )
    session.add(source)
    session.commit()

    source.display_name = "After update"
    session.commit()

    assert source.created_at == dt.datetime(2026, 9, 15, 14, 0, tzinfo=dt.UTC)
    assert source.updated_at > source.created_at


def test_source_rejects_blank_required_strings() -> None:
    with pytest.raises(ValueError, match="must not be blank"):
        Source(
            id=" ",
            kind="hermes",
            scope_id="scope-opaque-1",
            display_name="Configured Hermes",
        )


def test_source_enforces_primary_and_kind_scope_identities(session) -> None:
    session.add(
        Source(
            id="source-opaque-1",
            kind="hermes",
            scope_id="scope-opaque-1",
            display_name="First configured Hermes",
        )
    )
    session.commit()
    session.add(
        Source(
            id="source-opaque-2",
            kind="hermes",
            scope_id="scope-opaque-1",
            display_name="Second configured Hermes",
        )
    )

    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()

    session.add(
        Source(
            id="source-opaque-1",
            kind="pi",
            scope_id="scope-opaque-1",
            display_name="Configured Pi",
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()

    session.add(
        Source(
            id="source-opaque-3",
            kind="pi",
            scope_id="scope-opaque-1",
            display_name="Configured Pi",
        )
    )
    session.commit()


def test_utc_now_returns_an_aware_utc_timestamp() -> None:
    assert utc_now().tzinfo is dt.UTC
