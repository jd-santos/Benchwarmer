"""Scrub raw Pi sessions and check candidate fixtures without storing anything.

These routes take session content in the request body so a private session
never has to be imported before it is anonymized. They parse in memory, run the
deterministic scrub and checks, and keep no copy.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, StringConstraints

from benchwarmer.adapters.file_conversations import FileConversationError
from benchwarmer.adapters.pi.reader import parse_pi_session
from benchwarmer.anonymize import (
    FixtureCheck,
    FixtureConversation,
    ScrubReport,
    TermList,
    fidelity_issues,
    leak_issues,
    scrub_file_conversation,
)
from benchwarmer.api.routes.conversations import EventResponse

MAX_SESSION_CHARS = 16 * 1024 * 1024

SessionContent = Annotated[
    str, StringConstraints(min_length=1, max_length=MAX_SESSION_CHARS)
]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ScrubPiSessionRequest(_Strict):
    """Complete Pi session JSONL plus operator terms to scrub."""

    content: SessionContent
    terms: TermList = []


class ScrubPiSessionResponse(_Strict):
    """Scrubbed normalized events and the fixture they form; nothing is stored."""

    native_id: str
    source_version: str | None
    title: str | None
    events: list[EventResponse]
    fixture: FixtureConversation
    report: ScrubReport


class FixtureCheckRequest(_Strict):
    """One candidate fixture conversation and the raw session it must mirror."""

    content: SessionContent
    candidate: FixtureConversation
    terms: TermList = []


def _parse(content: str):
    try:
        return parse_pi_session(content)
    except FileConversationError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None


def create_fixtures_router() -> APIRouter:
    """Create the fixture routes; they never open the database."""
    router = APIRouter()

    @router.post("/fixtures/scrub-pi-session", response_model=ScrubPiSessionResponse)
    def scrub_pi_session(request: ScrubPiSessionRequest) -> ScrubPiSessionResponse:
        """Replace private-looking spans with placeholders; read-only, no model work."""
        result, _ = scrub_file_conversation(
            _parse(request.content), terms=request.terms
        )
        return ScrubPiSessionResponse(
            native_id=result.report.native_id,
            source_version=result.report.source_version,
            title=result.title,
            events=[EventResponse.model_validate(item) for item in result.events],
            fixture=result.fixture,
            report=result.report,
        )

    @router.post("/fixtures/check", response_model=FixtureCheck)
    def check_fixture(request: FixtureCheckRequest) -> FixtureCheck:
        """Report structural drift and private-text leaks against the raw session."""
        scrubbed, scrubber = scrub_file_conversation(
            _parse(request.content), terms=request.terms
        )
        fidelity = fidelity_issues(scrubbed.fixture, request.candidate)
        leaks = leak_issues(
            request.candidate, terms=request.terms, originals=scrubber.originals()
        )
        return FixtureCheck(
            native_id=scrubbed.report.native_id,
            fidelity=fidelity,
            leaks=leaks,
            ok=not fidelity and not leaks,
        )

    return router
