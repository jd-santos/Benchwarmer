"""Operator routes for named scrub term lists.

Every route here is operator-only: the terms are private data, and only
``GET /scrub-terms/{name}`` returns them. The list route returns counts.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
import datetime as dt
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from benchwarmer.anonymize import MAX_TERMS
from benchwarmer.config import BenchwarmerSettings
from benchwarmer.db import create_engine, create_session_factory
from benchwarmer.services.scrub_terms import (
    MAX_NOTES_LENGTH,
    MAX_TERM_LENGTH,
    NAME_PATTERN,
    TermListDetail,
    TermListInvalid,
    TermListNotFound,
    TermListRetired,
    TermListSummary,
    get_term_list,
    list_term_lists,
    retire_term_list,
    save_term_list,
)


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


ListName = Annotated[str, Path(pattern=NAME_PATTERN)]


class TermListSummaryResponse(_Strict):
    """One list's latest version; counts only, never the terms."""

    name: str
    version: int
    term_count: int
    notes: str | None
    created_at: dt.datetime
    retired_at: dt.datetime | None


class TermListDetailResponse(TermListSummaryResponse):
    """One list version with its terms; operator-only."""

    terms: list[str]


class TermListsResponse(_Strict):
    items: list[TermListSummaryResponse]


class TermListSaveRequest(_Strict):
    """Create a list or save its next version; the limit matches the scrubber's."""

    terms: Annotated[
        list[Annotated[str, Field(max_length=MAX_TERM_LENGTH)]],
        Field(max_length=MAX_TERMS),
    ]
    notes: Annotated[str, Field(max_length=MAX_NOTES_LENGTH)] | None = None


def _summary_response(item: TermListSummary) -> TermListSummaryResponse:
    return TermListSummaryResponse(
        name=item.name,
        version=item.version,
        term_count=item.term_count,
        notes=item.notes,
        created_at=item.created_at,
        retired_at=item.retired_at,
    )


def _detail_response(item: TermListDetail) -> TermListDetailResponse:
    return TermListDetailResponse(
        name=item.name,
        version=item.version,
        term_count=item.term_count,
        notes=item.notes,
        created_at=item.created_at,
        retired_at=item.retired_at,
        terms=list(item.terms),
    )


def create_scrub_terms_router(settings: BenchwarmerSettings) -> APIRouter:
    """Create the term list routes for one resolved runtime configuration."""
    router = APIRouter()

    @contextmanager
    def session_scope() -> Iterator[Session]:
        engine = create_engine(settings)
        factory: Callable[[], Session] = create_session_factory(engine)
        try:
            with factory() as session:
                yield session
        finally:
            engine.dispose()

    @router.get("/scrub-terms", response_model=TermListsResponse)
    def get_lists(include_retired: bool = False) -> TermListsResponse:
        with session_scope() as session:
            return TermListsResponse(
                items=[
                    _summary_response(item)
                    for item in list_term_lists(
                        session, include_retired=include_retired
                    )
                ]
            )

    @router.get("/scrub-terms/{name}", response_model=TermListDetailResponse)
    def get_list(
        name: ListName, version: Annotated[int | None, Query(ge=1)] = None
    ) -> TermListDetailResponse:
        with session_scope() as session:
            try:
                return _detail_response(get_term_list(session, name, version=version))
            except TermListNotFound:
                raise HTTPException(
                    status_code=404, detail="Term list not found"
                ) from None

    @router.put(
        "/scrub-terms/{name}",
        response_model=TermListDetailResponse,
        responses={
            409: {"description": "The list is retired"},
            422: {"description": "The list cannot be saved as given"},
        },
    )
    def put_list(
        name: ListName, request: TermListSaveRequest
    ) -> TermListDetailResponse | JSONResponse:
        with session_scope() as session:
            try:
                return _detail_response(
                    save_term_list(
                        session, name, terms=request.terms, notes=request.notes
                    )
                )
            except TermListRetired:
                return JSONResponse(
                    status_code=409,
                    content={"detail": "A retired term list cannot be saved again"},
                )
            except TermListInvalid as error:
                return JSONResponse(
                    status_code=422,
                    content={"detail": "Term list is invalid", "message": str(error)},
                )

    @router.post("/scrub-terms/{name}/retire", response_model=TermListSummaryResponse)
    def post_retire(name: ListName) -> TermListSummaryResponse:
        with session_scope() as session:
            try:
                return _summary_response(retire_term_list(session, name))
            except TermListNotFound:
                raise HTTPException(
                    status_code=404, detail="Term list not found"
                ) from None

    return router
