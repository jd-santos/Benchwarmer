"""Configured source identities and their baseline coverage declarations."""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping
from types import MappingProxyType
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    JSON,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    text,
)
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


class NativeSnapshot(Base):
    """Immutable private raw-source snapshot referenced by imported records."""

    __tablename__ = "native_snapshots"
    __table_args__ = (
        CheckConstraint("length(trim(id)) > 0", name="ck_native_snapshots_id_nonblank"),
        CheckConstraint(
            "length(trim(content_sha256)) = 64",
            name="ck_native_snapshots_hash_length",
        ),
        CheckConstraint(
            "byte_length >= 0", name="ck_native_snapshots_byte_length_nonnegative"
        ),
        UniqueConstraint(
            "source_id",
            "content_sha256",
            name="uq_native_snapshots_source_hash",
        ),
    )

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    source_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("sources.id", ondelete="RESTRICT", onupdate="RESTRICT"),
        nullable=False,
        index=True,
    )
    import_batch_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("import_batches.id", ondelete="RESTRICT", onupdate="RESTRICT"),
        nullable=False,
        index=True,
    )
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    relative_path: Mapped[str] = mapped_column(Text(), nullable=False)
    byte_length: Mapped[int] = mapped_column(Integer(), nullable=False)
    captured_at: Mapped[dt.datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utc_now
    )
    created_at: Mapped[dt.datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=utc_now,
        server_default=text("CURRENT_TIMESTAMP"),
    )


class NativeSession(Base):
    """Latest source-native session observation for one source scope."""

    __tablename__ = "native_sessions"
    __table_args__ = (
        PrimaryKeyConstraint("source_id", "native_id"),
        CheckConstraint(
            "length(trim(native_id)) > 0", name="ck_native_sessions_id_nonblank"
        ),
    )

    source_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("sources.id", ondelete="RESTRICT", onupdate="RESTRICT"),
        nullable=False,
    )
    native_id: Mapped[str] = mapped_column(String(255), nullable=False)
    parent_native_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_version: Mapped[str | None] = mapped_column(String(255), nullable=True)
    schema_version: Mapped[int] = mapped_column(Integer(), nullable=False)
    application_version: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON(), nullable=False)
    snapshot_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("native_snapshots.id", ondelete="RESTRICT", onupdate="RESTRICT"),
        nullable=False,
    )
    source_present: Mapped[bool] = mapped_column(
        Boolean(), nullable=False, default=True, server_default=text("1")
    )
    first_seen_at: Mapped[dt.datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utc_now
    )
    last_seen_at: Mapped[dt.datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utc_now
    )


class NativeMessage(Base):
    """Latest imported message observation keyed by source-native identity."""

    __tablename__ = "native_messages"
    __table_args__ = (
        PrimaryKeyConstraint("source_id", "native_id"),
        CheckConstraint(
            "length(trim(native_id)) > 0", name="ck_native_messages_id_nonblank"
        ),
        CheckConstraint(
            "length(trim(session_native_id)) > 0",
            name="ck_native_messages_session_nonblank",
        ),
        ForeignKeyConstraint(
            ["source_id", "session_native_id"],
            ["native_sessions.source_id", "native_sessions.native_id"],
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
    )

    source_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("sources.id", ondelete="RESTRICT", onupdate="RESTRICT"),
        nullable=False,
    )
    native_id: Mapped[str] = mapped_column(String(255), nullable=False)
    native_order: Mapped[int] = mapped_column(Integer(), nullable=False)
    session_native_id: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(64), nullable=False)
    content: Mapped[str | None] = mapped_column(Text(), nullable=True)
    tool_call_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tool_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reasoning: Mapped[str | None] = mapped_column(Text(), nullable=True)
    source_timestamp: Mapped[float] = mapped_column(Float(), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON(), nullable=False)
    snapshot_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("native_snapshots.id", ondelete="RESTRICT", onupdate="RESTRICT"),
        nullable=False,
    )
    source_present: Mapped[bool] = mapped_column(
        Boolean(), nullable=False, default=True, server_default=text("1")
    )
    first_seen_at: Mapped[dt.datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utc_now
    )
    last_seen_at: Mapped[dt.datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utc_now
    )


class NativeUsage(Base):
    """Latest source-native aggregate usage observation."""

    __tablename__ = "native_usages"
    __table_args__ = (
        PrimaryKeyConstraint(
            "source_id",
            "session_native_id",
            "model",
            "billing_provider",
            "billing_base_url",
            "billing_mode",
            "task",
        ),
        CheckConstraint(
            "length(trim(session_native_id)) > 0",
            name="ck_native_usages_session_nonblank",
        ),
        ForeignKeyConstraint(
            ["source_id", "session_native_id"],
            ["native_sessions.source_id", "native_sessions.native_id"],
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
    )

    source_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("sources.id", ondelete="RESTRICT", onupdate="RESTRICT"),
        nullable=False,
    )
    session_native_id: Mapped[str] = mapped_column(String(255), nullable=False)
    model: Mapped[str] = mapped_column(String(255), nullable=False)
    billing_provider: Mapped[str] = mapped_column(String(255), nullable=False)
    billing_base_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    billing_mode: Mapped[str] = mapped_column(String(255), nullable=False)
    task: Mapped[str] = mapped_column(String(255), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON(), nullable=False)
    snapshot_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("native_snapshots.id", ondelete="RESTRICT", onupdate="RESTRICT"),
        nullable=False,
    )
    source_present: Mapped[bool] = mapped_column(
        Boolean(), nullable=False, default=True, server_default=text("1")
    )
    first_seen_at: Mapped[dt.datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utc_now
    )
    last_seen_at: Mapped[dt.datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utc_now
    )


class ConversationRevision(Base):
    """Versioned normalized conversation document backed by native evidence."""

    __tablename__ = "conversation_revisions"
    __table_args__ = (
        CheckConstraint(
            "length(trim(id)) > 0", name="ck_conversation_revisions_id_nonblank"
        ),
        CheckConstraint(
            "length(trim(native_id)) > 0",
            name="ck_conversation_revisions_native_id_nonblank",
        ),
        UniqueConstraint(
            "source_id",
            "native_id",
            "revision",
            name="uq_conversation_revisions_source_native_revision",
        ),
    )

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    source_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("sources.id", ondelete="RESTRICT", onupdate="RESTRICT"),
        nullable=False,
        index=True,
    )
    native_id: Mapped[str] = mapped_column(String(255), nullable=False)
    revision: Mapped[str] = mapped_column(String(64), nullable=False)
    snapshot_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("native_snapshots.id", ondelete="RESTRICT", onupdate="RESTRICT"),
        nullable=False,
    )
    document: Mapped[dict[str, Any]] = mapped_column(JSON(), nullable=False)
    captured_at: Mapped[dt.datetime] = mapped_column(UTCDateTime(), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=utc_now,
        server_default=text("CURRENT_TIMESTAMP"),
    )


class SourcePresence(Base):
    """Bounded observation that a source-native subject was present."""

    __tablename__ = "source_presence"
    __table_args__ = (
        PrimaryKeyConstraint("source_id", "batch_id", "subject_kind", "native_id"),
    )

    source_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("sources.id", ondelete="RESTRICT", onupdate="RESTRICT"),
        nullable=False,
    )
    batch_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("import_batches.id", ondelete="RESTRICT", onupdate="RESTRICT"),
        nullable=False,
    )
    subject_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    native_id: Mapped[str] = mapped_column(String(255), nullable=False)
    present: Mapped[bool] = mapped_column(Boolean(), nullable=False)
    observed_at: Mapped[dt.datetime] = mapped_column(UTCDateTime(), nullable=False)


class SourceImportState(Base):
    """Current adapter cursor for one configured source scope."""

    __tablename__ = "source_import_states"
    __table_args__ = (
        CheckConstraint(
            "length(trim(adapter_version)) > 0",
            name="ck_source_import_states_adapter_nonblank",
        ),
    )

    source_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("sources.id", ondelete="RESTRICT", onupdate="RESTRICT"),
        primary_key=True,
    )
    adapter_version: Mapped[str] = mapped_column(String(64), nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer(), nullable=False)
    cursor: Mapped[dict[str, Any]] = mapped_column(JSON(), nullable=False)
    updated_at: Mapped[dt.datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
        server_default=text("CURRENT_TIMESTAMP"),
    )
