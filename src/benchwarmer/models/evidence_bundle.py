"""Evidence bundles and their immutable revisions."""

from __future__ import annotations

import datetime as dt
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    ForeignKey,
    Integer,
    PrimaryKeyConstraint,
    String,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from benchwarmer.models.base import Base
from benchwarmer.models.source import UTCDateTime, utc_now


class EvidenceBundle(Base):
    """A bundle identity; its content lives in numbered revisions."""

    __tablename__ = "evidence_bundles"
    __table_args__ = (
        CheckConstraint("length(trim(id)) > 0", name="ck_evidence_bundles_id_nonblank"),
        CheckConstraint(
            "latest_revision >= 1", name="ck_evidence_bundles_latest_positive"
        ),
    )

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    latest_revision: Mapped[int] = mapped_column(Integer(), nullable=False)
    # A client-supplied idempotency key for creation; a retry returns the same bundle.
    request_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True, unique=True, index=True
    )
    created_at: Mapped[dt.datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=utc_now,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utc_now
    )


class EvidenceBundleRevision(Base):
    """One immutable, validated bundle document and who produced it."""

    __tablename__ = "evidence_bundle_revisions"
    __table_args__ = (
        PrimaryKeyConstraint("bundle_id", "number"),
        CheckConstraint("number >= 1", name="ck_evidence_bundle_revisions_number"),
        CheckConstraint(
            "origin IN ('human', 'generated')",
            name="ck_evidence_bundle_revisions_origin",
        ),
    )

    bundle_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("evidence_bundles.id", ondelete="RESTRICT", onupdate="RESTRICT"),
        nullable=False,
    )
    number: Mapped[int] = mapped_column(Integer(), nullable=False)
    document: Mapped[dict[str, Any]] = mapped_column(JSON(), nullable=False)
    origin: Mapped[str] = mapped_column(String(32), nullable=False)
    producer: Mapped[str] = mapped_column(String(255), nullable=False)
    # Run-level provenance for generated revisions; see ``benchwarmer.evidence.RunProvenance``.
    provenance: Mapped[dict[str, Any] | None] = mapped_column(JSON(), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utc_now
    )
