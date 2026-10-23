"""Typed records of hand-run harness workflows and their model usage.

A harness run is the approval boundary for model work until the bounded
model-work service exists, so the application keeps a record of each run: the
workflow, model, endpoint, inputs, which bundles each input produced, raw token
usage, and the catalog estimate with its pricing source. Cost figures here are
estimates from the harness's model catalog, not provider charges.
"""

from __future__ import annotations

import datetime as dt
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints

_Identifier = Annotated[str, StringConstraints(min_length=1, max_length=255)]
_Note = Annotated[str, StringConstraints(strip_whitespace=True, max_length=4000)]
_Url = Annotated[str, StringConstraints(min_length=1, max_length=1024)]


def _iso_timestamp(value: str) -> str:
    dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    return value


_Timestamp = Annotated[str, AfterValidator(_iso_timestamp)]

RunInputKind = Literal["conversation", "session"]
RunInputStatus = Literal["done", "unanswered", "error"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class UsageCost(_Strict):
    """Estimated cost in USD per token class."""

    input: float
    output: float
    cache_read: float
    cache_write: float
    total: float


class ModelUsage(_Strict):
    """Raw token counts for one model or tool and their estimated cost."""

    input: int
    output: int
    cache_read: int
    cache_write: int
    total_tokens: int
    cost: UsageCost


class UsageTotal(_Strict):
    """Usage by model and by tool, keyed by ``provider/model-id`` or tool name."""

    models: dict[_Identifier, ModelUsage] = {}
    tools: dict[_Identifier, ModelUsage] = {}

    @property
    def total_tokens(self) -> int:
        return sum(usage.total_tokens for usage in self.models.values())

    @property
    def estimated_cost(self) -> float:
        return sum(usage.cost.total for usage in self.models.values()) + sum(
            usage.cost.total for usage in self.tools.values()
        )


class RunInput(_Strict):
    """One conversation or session the run worked on and what came of it."""

    id: _Identifier
    kind: RunInputKind
    status: RunInputStatus
    reason: _Note | None = None
    bundle_ids: Annotated[list[_Identifier], Field(max_length=500)] = []
    usage: UsageTotal


class RunModel(_Strict):
    provider: _Identifier
    model_id: _Identifier
    thinking_level: _Identifier | None = None
    # Where requests went when the operator redirected the provider, else None.
    base_url_override: _Url | None = None


class HarnessRunRecord(_Strict):
    """The record a harness workflow sends when it finishes."""

    run_id: _Identifier
    workflow: _Identifier
    harness_version: _Identifier
    started_at: _Timestamp
    finished_at: _Timestamp
    api_base_url: _Url
    model: RunModel
    producer: _Identifier
    inputs: Annotated[list[RunInput], Field(max_length=1000)]
    usage_total: UsageTotal
    pricing_source: _Note
    report_path: _Url | None = None

    @property
    def bundle_count(self) -> int:
        return sum(len(item.bundle_ids) for item in self.inputs)


def parse_timestamp(value: str) -> dt.datetime:
    """Parse an ISO 8601 timestamp, treating ``Z`` as UTC."""
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.UTC)
    return parsed.astimezone(dt.UTC)
