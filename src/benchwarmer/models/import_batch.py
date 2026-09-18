"""Durable import attempts and their cursor and coverage provenance."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import datetime as dt
import json
import math
from types import MappingProxyType
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    JSON,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, validates
from sqlalchemy.types import TypeDecorator

from benchwarmer.models.base import Base
from benchwarmer.models.source import UTCDateTime, _normalize_utc, utc_now

_IMPORT_OUTCOMES = frozenset({"failed", "partial", "succeeded"})
_COVERAGE_STATES = frozenset(
    {"available", "partial", "unavailable", "unknown", "redacted"}
)
_MAX_COVERAGE_DIMENSIONS = 64
_MAX_COVERAGE_DIMENSION_NAME_LENGTH = 128
_MAX_CURSOR_STORAGE_LENGTH = 16_384
_MAX_ERROR_SUMMARY_LENGTH = 2_000


def _validate_json_value(value: object, active: set[int] | None = None) -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("invalid import cursor")
        return
    if not isinstance(value, (list, dict)):
        raise ValueError("invalid import cursor")

    if active is None:
        active = set()
    marker = id(value)
    if marker in active:
        raise ValueError("invalid import cursor")
    active.add(marker)
    try:
        if isinstance(value, list):
            for item in value:
                _validate_json_value(item, active)
        else:
            for key, item in value.items():
                if not isinstance(key, str):
                    raise ValueError("invalid import cursor")
                _validate_json_value(item, active)
    except RecursionError as error:
        raise ValueError("invalid import cursor") from error
    finally:
        active.remove(marker)


def _canonical_json_copy(value: object) -> object:
    _validate_json_value(value)
    try:
        encoded = json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError, RecursionError) as error:
        raise ValueError("invalid import cursor") from error
    if len(encoded.encode("utf-8")) > _MAX_CURSOR_STORAGE_LENGTH:
        raise ValueError("invalid import cursor")
    return json.loads(encoded)


class ImportCursor:
    """A bounded, versioned copy of an adapter-specific import cursor."""

    __slots__ = ("_value",)

    def __init__(self, value: object) -> None:
        self._value = _canonical_json_copy(value)

    @property
    def schema_version(self) -> int:
        return 1

    @property
    def value(self) -> Any:
        """Return a copy so callers cannot mutate persisted cursor state."""
        return deepcopy(self._value)

    @classmethod
    def from_mapping(cls, value: object) -> ImportCursor:
        if (
            not isinstance(value, Mapping)
            or set(value) != {"schema_version", "value"}
            or type(value["schema_version"]) is not int
            or value["schema_version"] != 1
        ):
            raise ValueError("invalid import cursor envelope")
        return cls(value["value"])

    def to_storage(self) -> dict[str, object]:
        return {"schema_version": 1, "value": self.value}

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ImportCursor):
            return NotImplemented
        return self._value == other._value

    def __repr__(self) -> str:
        return f"ImportCursor(value={self._value!r})"


class ImportCursorType(TypeDecorator[ImportCursor]):
    """Persist only validated version-one cursor envelopes."""

    impl = JSON(none_as_null=True)
    cache_ok = True

    def process_bind_param(
        self, value: ImportCursor | None, dialect: Any
    ) -> dict[str, object] | None:
        del dialect
        if value is None:
            return None
        if not isinstance(value, ImportCursor):
            raise ValueError("import cursor must be ImportCursor")
        return value.to_storage()

    def process_result_value(self, value: object, dialect: Any) -> ImportCursor | None:
        del dialect
        if value is None:
            return None
        return ImportCursor.from_mapping(value)


class ImportCoverage:
    """Immutable observed coverage for one import attempt."""

    __slots__ = ("_dimensions",)

    def __init__(self, dimensions: Mapping[str, str]) -> None:
        if len(dimensions) > _MAX_COVERAGE_DIMENSIONS:
            raise ValueError("invalid import coverage dimensions")
        validated: dict[str, str] = {}
        for name, state in dimensions.items():
            if (
                not isinstance(name, str)
                or not name.strip()
                or len(name) > _MAX_COVERAGE_DIMENSION_NAME_LENGTH
                or not isinstance(state, str)
                or state not in _COVERAGE_STATES
            ):
                raise ValueError("invalid import coverage dimension")
            validated[name] = state
        self._dimensions = MappingProxyType(validated)

    @property
    def schema_version(self) -> int:
        return 1

    @property
    def dimensions(self) -> Mapping[str, str]:
        return self._dimensions

    @classmethod
    def from_mapping(cls, value: object) -> ImportCoverage:
        if (
            not isinstance(value, Mapping)
            or set(value) != {"schema_version", "dimensions"}
            or type(value["schema_version"]) is not int
            or value["schema_version"] != 1
            or not isinstance(value["dimensions"], Mapping)
        ):
            raise ValueError("invalid import coverage envelope")
        return cls(value["dimensions"])

    def to_storage(self) -> dict[str, object]:
        return {"schema_version": 1, "dimensions": dict(self._dimensions)}

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ImportCoverage):
            return NotImplemented
        return self._dimensions == other._dimensions

    def __repr__(self) -> str:
        return f"ImportCoverage(dimensions={dict(self._dimensions)!r})"


class ImportCoverageType(TypeDecorator[ImportCoverage]):
    """Persist only validated version-one observed-coverage envelopes."""

    impl = JSON(none_as_null=True)
    cache_ok = True

    def process_bind_param(
        self, value: ImportCoverage | None, dialect: Any
    ) -> dict[str, object] | None:
        del dialect
        if value is None:
            return None
        if not isinstance(value, ImportCoverage):
            raise ValueError("import coverage must be ImportCoverage")
        return value.to_storage()

    def process_result_value(
        self, value: object, dialect: Any
    ) -> ImportCoverage | None:
        del dialect
        if value is None:
            return None
        return ImportCoverage.from_mapping(value)


class ImportBatch(Base):
    """One terminal import attempt for a configured source."""

    __tablename__ = "import_batches"
    __table_args__ = (
        CheckConstraint("length(trim(id)) > 0", name="ck_import_batches_id_nonblank"),
        CheckConstraint(
            "length(trim(source_id)) > 0",
            name="ck_import_batches_source_id_nonblank",
        ),
        CheckConstraint(
            "length(trim(idempotency_key)) > 0",
            name="ck_import_batches_idempotency_key_nonblank",
        ),
        CheckConstraint(
            "outcome IN ('failed', 'partial', 'succeeded')",
            name="ck_import_batches_outcome",
        ),
        CheckConstraint(
            "completed_at >= started_at",
            name="ck_import_batches_timestamp_order",
        ),
        CheckConstraint(
            "error_summary IS NULL OR "
            f"(length(trim(error_summary)) > 0 AND length(error_summary) <= {_MAX_ERROR_SUMMARY_LENGTH})",
            name="ck_import_batches_error_summary",
        ),
        CheckConstraint(
            "(outcome = 'failed' AND error_summary IS NOT NULL) OR "
            "(outcome = 'partial') OR "
            "(outcome = 'succeeded' AND error_summary IS NULL)",
            name="ck_import_batches_error_outcome",
        ),
        UniqueConstraint(
            "source_id",
            "idempotency_key",
            name="uq_import_batches_source_idempotency_key",
        ),
    )

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    source_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("sources.id", ondelete="RESTRICT", onupdate="RESTRICT"),
        nullable=False,
        index=True,
    )
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    cursor_before: Mapped[ImportCursor | None] = mapped_column(
        ImportCursorType(), nullable=True
    )
    cursor_after: Mapped[ImportCursor | None] = mapped_column(
        ImportCursorType(), nullable=True
    )
    observed_coverage: Mapped[ImportCoverage | None] = mapped_column(
        ImportCoverageType(), nullable=True
    )
    started_at: Mapped[dt.datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=utc_now,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    completed_at: Mapped[dt.datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=utc_now,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    error_summary: Mapped[str | None] = mapped_column(Text(), nullable=True)

    @validates("id", "source_id", "idempotency_key")
    def _validate_required_string(self, key: str, value: str) -> str:
        del key
        if not isinstance(value, str) or not value.strip():
            raise ValueError("required import batch strings must not be blank")
        return value

    @validates("outcome")
    def _validate_outcome(self, key: str, value: str) -> str:
        del key
        if not isinstance(value, str) or value not in _IMPORT_OUTCOMES:
            raise ValueError("invalid import outcome")
        return value

    @validates("started_at", "completed_at")
    def _validate_timestamp(self, key: str, value: dt.datetime) -> dt.datetime:
        del key
        return _normalize_utc(value)

    @validates("cursor_before", "cursor_after")
    def _validate_cursor(
        self, key: str, value: ImportCursor | Mapping[str, object] | None
    ) -> ImportCursor | None:
        del key
        if value is None or isinstance(value, ImportCursor):
            return value
        return ImportCursor.from_mapping(value)

    @validates("observed_coverage")
    def _validate_coverage(
        self, key: str, value: ImportCoverage | Mapping[str, object] | None
    ) -> ImportCoverage | None:
        del key
        if value is None or isinstance(value, ImportCoverage):
            return value
        return ImportCoverage.from_mapping(value)

    @validates("error_summary")
    def _validate_error_summary(self, key: str, value: str | None) -> str | None:
        del key
        if value is not None and (
            not isinstance(value, str)
            or not value.strip()
            or len(value) > _MAX_ERROR_SUMMARY_LENGTH
        ):
            raise ValueError("invalid import error summary")
        return value
