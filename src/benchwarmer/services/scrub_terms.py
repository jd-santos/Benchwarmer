"""Named, versioned term lists for the case export scrubber.

A term list is operator data: the names, customers, hosts, and project words
the built-in detector kinds cannot know. Lists are saved under a name and
every save that changes the terms or notes creates the next immutable
version, so an export can pin ``{name, version}`` and stay reproducible.
Summaries carry counts, never terms; only ``get_term_list`` returns them, and
nothing here logs or copies a term anywhere else.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
import datetime as dt
import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from benchwarmer.anonymize import MAX_TERMS
from benchwarmer.models.scrub_term_list import ScrubTermList
from benchwarmer.models.source import utc_now

NAME_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$"
MAX_TERM_LENGTH = 200
MAX_NOTES_LENGTH = 2000
_NAME = re.compile(NAME_PATTERN)


class TermListNotFound(LookupError):
    """Raised when no list, or no such version of a list, exists."""


class TermListRetired(RuntimeError):
    """Raised when a retired list is saved again."""


class TermListInvalid(ValueError):
    """Raised when a list cannot be saved as given; the message names no term."""


@dataclass(frozen=True)
class TermListSummary:
    """One version of a list without its terms."""

    name: str
    version: int
    term_count: int
    notes: str | None
    created_at: dt.datetime
    retired_at: dt.datetime | None


@dataclass(frozen=True)
class TermListDetail(TermListSummary):
    """A list version with its terms; for the operator route and the export."""

    terms: tuple[str, ...]


def normalize_terms(terms: Sequence[str]) -> tuple[str, ...]:
    """Strip, drop blanks, and remove case-insensitive repeats, keeping order.

    Raises ``TermListInvalid`` when a term is too long or the list exceeds the
    scrubber's per-call cap; the message counts, never quotes.
    """
    seen: set[str] = set()
    cleaned: list[str] = []
    for index, raw in enumerate(terms):
        term = raw.strip()
        if not term:
            continue
        if len(term) > MAX_TERM_LENGTH:
            raise TermListInvalid(
                f"term {index + 1} is longer than {MAX_TERM_LENGTH} characters"
            )
        key = term.casefold()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(term)
    if len(cleaned) > MAX_TERMS:
        raise TermListInvalid(
            f"{len(cleaned)} distinct terms exceed the limit of {MAX_TERMS}"
        )
    return tuple(cleaned)


def _summary(row: ScrubTermList) -> TermListSummary:
    return TermListSummary(
        name=row.name,
        version=row.version,
        term_count=len(row.terms),
        notes=row.notes,
        created_at=row.created_at,
        retired_at=row.retired_at,
    )


def _detail(row: ScrubTermList) -> TermListDetail:
    return TermListDetail(
        name=row.name,
        version=row.version,
        term_count=len(row.terms),
        notes=row.notes,
        created_at=row.created_at,
        retired_at=row.retired_at,
        terms=tuple(str(term) for term in row.terms),
    )


def _latest(session: Session, name: str) -> ScrubTermList | None:
    return session.execute(
        select(ScrubTermList)
        .where(ScrubTermList.name == name)
        .order_by(ScrubTermList.version.desc())
        .limit(1)
    ).scalar_one_or_none()


def list_term_lists(
    session: Session, *, include_retired: bool = False
) -> tuple[TermListSummary, ...]:
    """Summarize the latest version of every list, by name; no terms."""
    latest = (
        select(ScrubTermList.name, func.max(ScrubTermList.version).label("version"))
        .group_by(ScrubTermList.name)
        .subquery()
    )
    query = (
        select(ScrubTermList)
        .join(
            latest,
            (ScrubTermList.name == latest.c.name)
            & (ScrubTermList.version == latest.c.version),
        )
        .order_by(ScrubTermList.name)
    )
    if not include_retired:
        query = query.where(ScrubTermList.retired_at.is_(None))
    return tuple(_summary(row) for row in session.execute(query).scalars())


def get_term_list(
    session: Session, name: str, *, version: int | None = None
) -> TermListDetail:
    """Return one version of a list with its terms; the latest when unpinned."""
    if version is None:
        row = _latest(session, name)
    else:
        row = session.get(ScrubTermList, (name, version))
    if row is None:
        raise TermListNotFound(name)
    return _detail(row)


def save_term_list(
    session: Session, name: str, *, terms: Sequence[str], notes: str | None
) -> TermListDetail:
    """Create a list or its next version.

    An unchanged save (same terms in the same order, same notes) returns the
    latest version without writing. Saving a retired list is refused.
    """
    if not _NAME.match(name):
        raise TermListInvalid(
            "name must be 1 to 64 letters, digits, dots, dashes, or underscores"
        )
    cleaned = normalize_terms(terms)
    if not cleaned:
        raise TermListInvalid("a term list needs at least one term")
    clean_notes = notes.strip() if notes is not None and notes.strip() else None
    if clean_notes is not None and len(clean_notes) > MAX_NOTES_LENGTH:
        raise TermListInvalid(f"notes are longer than {MAX_NOTES_LENGTH} characters")
    latest = _latest(session, name)
    if latest is not None:
        if latest.retired_at is not None:
            raise TermListRetired(name)
        if tuple(latest.terms) == cleaned and latest.notes == clean_notes:
            return _detail(latest)
    row = ScrubTermList(
        name=name,
        version=1 if latest is None else latest.version + 1,
        terms=list(cleaned),
        notes=clean_notes,
        created_at=utc_now(),
        retired_at=None,
    )
    session.add(row)
    session.commit()
    return _detail(row)


def retire_term_list(session: Session, name: str) -> TermListSummary:
    """Mark every version of a list retired; pinned exports still resolve it."""
    rows = list(
        session.execute(
            select(ScrubTermList).where(ScrubTermList.name == name)
        ).scalars()
    )
    if not rows:
        raise TermListNotFound(name)
    now = utc_now()
    for row in rows:
        if row.retired_at is None:
            row.retired_at = now
    session.commit()
    return _summary(max(rows, key=lambda row: row.version))


__all__ = [
    "MAX_NOTES_LENGTH",
    "MAX_TERM_LENGTH",
    "NAME_PATTERN",
    "TermListDetail",
    "TermListInvalid",
    "TermListNotFound",
    "TermListRetired",
    "TermListSummary",
    "get_term_list",
    "list_term_lists",
    "normalize_terms",
    "retire_term_list",
    "save_term_list",
]
