"""Named, versioned lists of operator terms the case export scrubs."""

from __future__ import annotations

import datetime as dt
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Integer,
    PrimaryKeyConstraint,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from benchwarmer.models.base import Base
from benchwarmer.models.source import UTCDateTime, utc_now


class ScrubTermList(Base):
    """One immutable version of a named term list.

    The terms are operator data: they name people, customers, hosts, and
    projects, so they are read back only through the operator route and never
    copied into logs, exports, or a redaction manifest. Retiring a list marks
    every version of its name; an export may still pin a retired version so
    an old record stays reproducible.
    """

    __tablename__ = "scrub_term_lists"
    __table_args__ = (
        PrimaryKeyConstraint("name", "version"),
        CheckConstraint("length(trim(name)) > 0", name="ck_scrub_term_lists_name"),
        CheckConstraint("version >= 1", name="ck_scrub_term_lists_version"),
    )

    name: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(Integer(), nullable=False)
    terms: Mapped[list[Any]] = mapped_column(JSON(), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text(), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utc_now
    )
    retired_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime(), nullable=True)
