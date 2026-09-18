"""Configured source identities and their baseline coverage declarations."""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping
from types import MappingProxyType
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, JSON, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, validates
from sqlalchemy.types import TypeDecorator

from benchwarmer.models.base import Base

_COVERAGE_STATES = frozenset({"available", "partial", "unavailable", "unknown"})
_MAX_COVERAGE_DIMENSIONS = 64
_MAX_COVERAGE_DIMENSION_NAME_LENGTH = 128


def utc_now() -> dt.datetime:
    """Return Benchwarmer's current timestamp as an aware UTC datetime."""
    return dt.datetime.now(dt.UTC)


def _normalize_utc(value: dt.datetime) -> dt.datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamps must be UTC-aware")
    return value.astimezone(dt.UTC)


def _validated_dimensions(dimensions: Mapping[str, str]) -> dict[str, str]:
    if len(dimensions) > _MAX_COVERAGE_DIMENSIONS:
        raise ValueError("invalid configured coverage dimensions")

    validated: dict[str, str] = {}
    for name, state in dimensions.items():
        if (
            not isinstance(name, str)
            or not name.strip()
            or len(name) > _MAX_COVERAGE_DIMENSION_NAME_LENGTH
            or not isinstance(state, str)
            or state not in _COVERAGE_STATES
        ):
            raise ValueError("invalid configured coverage dimension")
        validated[name] = state
    return validated


class ConfiguredCoverage:
    """Immutable validated baseline coverage for one configured source."""

    __slots__ = ("_dimensions",)

    def __init__(self, dimensions: Mapping[str, str]) -> None:
        self._dimensions = MappingProxyType(_validated_dimensions(dimensions))

    @property
    def schema_version(self) -> int:
        """Return the persisted coverage-envelope schema version."""
        return 1

    @property
    def dimensions(self) -> Mapping[str, str]:
        """Return immutable configured coverage states by dimension."""
        return self._dimensions

    @classmethod
    def from_mapping(cls, value: object) -> ConfiguredCoverage:
        """Validate the exact version-one storage envelope."""
        if not isinstance(value, Mapping) or set(value) != {
            "schema_version",
            "dimensions",
        }:
            raise ValueError("invalid configured coverage envelope")
        if type(value["schema_version"]) is not int or value["schema_version"] != 1:
            raise ValueError("invalid configured coverage schema version")
        dimensions = value["dimensions"]
        if not isinstance(dimensions, Mapping):
            raise ValueError("invalid configured coverage dimensions")
        return cls(dimensions)

    def to_storage(self) -> dict[str, object]:
        """Return a fresh version-one JSON-compatible storage envelope."""
        return {"schema_version": 1, "dimensions": dict(self._dimensions)}

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ConfiguredCoverage):
            return NotImplemented
        return self._dimensions == other._dimensions

    def __repr__(self) -> str:
        return f"ConfiguredCoverage(dimensions={dict(self._dimensions)!r})"


class ConfiguredCoverageType(TypeDecorator[ConfiguredCoverage]):
    """Store only validated immutable configured-coverage envelopes."""

    impl = JSON(none_as_null=True)
    cache_ok = True

    def process_bind_param(
        self, value: ConfiguredCoverage | None, dialect: Any
    ) -> dict[str, object] | None:
        del dialect
        if value is None:
            return None
        if not isinstance(value, ConfiguredCoverage):
            raise ValueError("configured coverage must be ConfiguredCoverage")
        return value.to_storage()

    def process_result_value(
        self, value: object, dialect: Any
    ) -> ConfiguredCoverage | None:
        del dialect
        if value is None:
            return None
        return ConfiguredCoverage.from_mapping(value)


class UTCDateTime(TypeDecorator[dt.datetime]):
    """Store UTC datetimes in SQLite and restore them as aware UTC values."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(
        self, value: dt.datetime | None, dialect: Any
    ) -> dt.datetime | None:
        del dialect
        if value is None:
            return None
        return _normalize_utc(value).replace(tzinfo=None)

    def process_result_value(
        self, value: dt.datetime | None, dialect: Any
    ) -> dt.datetime | None:
        del dialect
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            return value.replace(tzinfo=dt.UTC)
        return value.astimezone(dt.UTC)


class Source(Base):
    """One explicitly configured source installation or profile."""

    __tablename__ = "sources"
    __table_args__ = (
        CheckConstraint("length(trim(id)) > 0", name="ck_sources_id_nonblank"),
        CheckConstraint("length(trim(kind)) > 0", name="ck_sources_kind_nonblank"),
        CheckConstraint(
            "length(trim(scope_id)) > 0", name="ck_sources_scope_id_nonblank"
        ),
        CheckConstraint(
            "length(trim(display_name)) > 0", name="ck_sources_display_name_nonblank"
        ),
        UniqueConstraint("kind", "scope_id", name="uq_sources_kind_scope_id"),
    )

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    kind: Mapped[str] = mapped_column(String(128), nullable=False)
    scope_id: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    configured_coverage: Mapped[ConfiguredCoverage | None] = mapped_column(
        ConfiguredCoverageType(), nullable=True
    )
    created_at: Mapped[dt.datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=utc_now,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    @validates("id", "kind", "scope_id", "display_name")
    def _validate_required_string(self, key: str, value: str) -> str:
        del key
        if not isinstance(value, str) or not value.strip():
            raise ValueError("required source strings must not be blank")
        return value

    @validates("created_at", "updated_at")
    def _validate_timestamp(self, key: str, value: dt.datetime) -> dt.datetime:
        del key
        return _normalize_utc(value)

    @validates("configured_coverage")
    def _validate_configured_coverage(
        self, key: str, value: ConfiguredCoverage | Mapping[str, object] | None
    ) -> ConfiguredCoverage | None:
        del key
        if value is None or isinstance(value, ConfiguredCoverage):
            return value
        return ConfiguredCoverage.from_mapping(value)
