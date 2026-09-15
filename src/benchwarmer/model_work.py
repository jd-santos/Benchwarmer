"""Bounded, in-memory model-work approval contracts.

This module validates a preview and its exact approval digest. It does not perform
permission lookup, price validation, dispatch, durable spend reservation, or
uncertain-outcome recovery. Those operations belong to a later service.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import hashlib
import json
from typing import Final, cast


class ModelWorkValidationError(ValueError):
    """Raised when a model-work contract is malformed or not exactly approved."""


_OPERATIONS: Final[frozenset[str]] = frozenset(
    {
        "classification",
        "description",
        "embedding",
        "query_embedding",
        "segmentation",
        "criteria",
        "rerun",
        "judge",
        "simulation",
    }
)
_SCHEMA_VERSION: Final[int] = 1
_MAX_DECIMAL_DIGITS: Final[int] = 1_000
_MAX_DECIMAL_EXPONENT_MAGNITUDE: Final[int] = 1_000

__all__ = [
    "ModelWorkValidationError",
    "WorkApproval",
    "WorkItem",
    "WorkPlan",
    "WorkStage",
    "plan_digest",
    "validate_approval",
]


def _invalid(field: str) -> None:
    """Raise a bounded error which does not include supplied values."""
    raise ModelWorkValidationError(field)


def _nonempty_string(value: object, field: str) -> None:
    if type(value) is not str or not value:
        _invalid(field)


def _nonnegative_int(value: object, field: str) -> None:
    if type(value) is not int or value < 0:
        _invalid(field)


def _positive_int(value: object, field: str) -> None:
    if type(value) is not int or value <= 0:
        _invalid(field)


def _canonical_decimal_parts(value: object, field: str) -> tuple[str, int]:
    """Return a context-independent, normalized nonnegative Decimal encoding."""
    if type(value) is not Decimal:
        _invalid(field)
    decimal_value = cast(Decimal, value)
    if not decimal_value.is_finite() or decimal_value < 0:
        _invalid(field)

    decimal_tuple = decimal_value.as_tuple()
    digits = decimal_tuple.digits
    if not any(digits):
        return ("0", 0)

    end = len(digits)
    exponent_value = decimal_tuple.exponent
    if not isinstance(exponent_value, int):
        _invalid(field)
    exponent = cast(int, exponent_value)
    while end > 0 and digits[end - 1] == 0:
        end -= 1
        exponent += 1
    if end > _MAX_DECIMAL_DIGITS or abs(exponent) > _MAX_DECIMAL_EXPONENT_MAGNITUDE:
        _invalid(field)
    return ("".join(str(digit) for digit in digits[:end]), exponent)


def _coefficient_as_int(coefficient: str) -> int:
    result = 0
    for digit in coefficient:
        result = result * 10 + ord(digit) - ord("0")
    return result


def _costs_at_least_common_exponent(
    costs: tuple[Decimal, ...], total: Decimal
) -> tuple[int, int]:
    """Return integer coefficients for summed costs and the total at one exponent."""
    cost_parts = tuple(
        _canonical_decimal_parts(cost, "stages.max_cost") for cost in costs
    )
    total_coefficient, total_exponent = _canonical_decimal_parts(
        total, "max_total_cost"
    )
    exponent = min((part[1] for part in cost_parts), default=total_exponent)
    exponent = min(exponent, total_exponent)
    stage_sum = sum(
        _coefficient_as_int(coefficient) * 10 ** (part_exponent - exponent)
        for coefficient, part_exponent in cost_parts
    )
    total_value = _coefficient_as_int(total_coefficient) * 10 ** (
        total_exponent - exponent
    )
    return stage_sum, total_value


@dataclass(frozen=True, slots=True)
class WorkItem:
    input_id: str
    input_revision: str

    def __post_init__(self) -> None:
        _validate_item(self)


def _validate_item(item: object) -> None:
    if type(item) is not WorkItem:
        _invalid("items")
    checked_item = cast(WorkItem, item)
    _nonempty_string(checked_item.input_id, "input_id")
    _nonempty_string(checked_item.input_revision, "input_revision")


@dataclass(frozen=True, slots=True)
class WorkStage:
    stage_id: str
    operation: str
    provider: str
    model: str
    configuration_digest: str
    input_manifest_digest: str
    max_requests: int
    max_input_tokens: int
    max_output_tokens: int
    max_cost: Decimal

    def __post_init__(self) -> None:
        _validate_stage(self)


def _validate_stage(stage: object) -> None:
    if type(stage) is not WorkStage:
        _invalid("stages")
    checked_stage = cast(WorkStage, stage)
    _nonempty_string(checked_stage.stage_id, "stage_id")
    if (
        type(checked_stage.operation) is not str
        or checked_stage.operation not in _OPERATIONS
    ):
        _invalid("operation")
    _nonempty_string(checked_stage.provider, "provider")
    _nonempty_string(checked_stage.model, "model")
    _nonempty_string(checked_stage.configuration_digest, "configuration_digest")
    _nonempty_string(checked_stage.input_manifest_digest, "input_manifest_digest")
    _positive_int(checked_stage.max_requests, "max_requests")
    _nonnegative_int(checked_stage.max_input_tokens, "max_input_tokens")
    _nonnegative_int(checked_stage.max_output_tokens, "max_output_tokens")
    _canonical_decimal_parts(checked_stage.max_cost, "max_cost")


@dataclass(frozen=True, slots=True)
class WorkPlan:
    schema_version: int
    items: tuple[WorkItem, ...]
    stages: tuple[WorkStage, ...]
    currency: str
    max_total_cost: Decimal
    max_total_requests: int
    max_concurrency: int
    pricing_basis: str
    disclosure_scope: str

    def __post_init__(self) -> None:
        _validate_plan(self)


@dataclass(frozen=True, slots=True)
class WorkApproval:
    plan_digest: str
    approved_by: str

    def __post_init__(self) -> None:
        _validate_approval_record(self)


def _validate_approval_record(approval: object) -> None:
    if type(approval) is not WorkApproval:
        _invalid("approval")
    checked_approval = cast(WorkApproval, approval)
    _nonempty_string(checked_approval.plan_digest, "approval.plan_digest")
    _nonempty_string(checked_approval.approved_by, "approval.approved_by")


def _validate_plan(plan: object) -> None:
    if type(plan) is not WorkPlan:
        _invalid("plan")
    checked_plan = cast(WorkPlan, plan)
    if (
        type(checked_plan.schema_version) is not int
        or checked_plan.schema_version != _SCHEMA_VERSION
    ):
        _invalid("schema_version")
    if type(checked_plan.items) is not tuple or not checked_plan.items:
        _invalid("items")
    if type(checked_plan.stages) is not tuple or not checked_plan.stages:
        _invalid("stages")
    for item in checked_plan.items:
        _validate_item(item)
    for stage in checked_plan.stages:
        _validate_stage(stage)

    item_identities = {
        (item.input_id, item.input_revision) for item in checked_plan.items
    }
    if len(item_identities) != len(checked_plan.items):
        _invalid("items")
    stage_ids = {stage.stage_id for stage in checked_plan.stages}
    if len(stage_ids) != len(checked_plan.stages):
        _invalid("stages")

    _nonempty_string(checked_plan.currency, "currency")
    if (
        len(checked_plan.currency) != 3
        or checked_plan.currency != checked_plan.currency.upper()
        or not checked_plan.currency.isascii()
        or not checked_plan.currency.isalpha()
    ):
        _invalid("currency")
    _canonical_decimal_parts(checked_plan.max_total_cost, "max_total_cost")
    _positive_int(checked_plan.max_total_requests, "max_total_requests")
    _positive_int(checked_plan.max_concurrency, "max_concurrency")
    _nonempty_string(checked_plan.pricing_basis, "pricing_basis")
    _nonempty_string(checked_plan.disclosure_scope, "disclosure_scope")

    request_total = sum(stage.max_requests for stage in checked_plan.stages)
    if request_total > checked_plan.max_total_requests:
        _invalid("max_total_requests")
    if checked_plan.max_concurrency > checked_plan.max_total_requests:
        _invalid("max_concurrency")
    stage_cost, total_cost = _costs_at_least_common_exponent(
        tuple(stage.max_cost for stage in checked_plan.stages),
        checked_plan.max_total_cost,
    )
    if stage_cost > total_cost:
        _invalid("max_total_cost")


def _canonical_plan(plan: WorkPlan) -> dict[str, object]:
    def decimal_value(value: Decimal, field: str) -> dict[str, object]:
        coefficient, exponent = _canonical_decimal_parts(value, field)
        return {"coefficient": coefficient, "exponent": exponent}

    return {
        "schema_version": plan.schema_version,
        "items": [
            {"input_id": item.input_id, "input_revision": item.input_revision}
            for item in plan.items
        ],
        "stages": [
            {
                "stage_id": stage.stage_id,
                "operation": stage.operation,
                "provider": stage.provider,
                "model": stage.model,
                "configuration_digest": stage.configuration_digest,
                "input_manifest_digest": stage.input_manifest_digest,
                "max_requests": stage.max_requests,
                "max_input_tokens": stage.max_input_tokens,
                "max_output_tokens": stage.max_output_tokens,
                "max_cost": decimal_value(stage.max_cost, "max_cost"),
            }
            for stage in plan.stages
        ],
        "currency": plan.currency,
        "max_total_cost": decimal_value(plan.max_total_cost, "max_total_cost"),
        "max_total_requests": plan.max_total_requests,
        "max_concurrency": plan.max_concurrency,
        "pricing_basis": plan.pricing_basis,
        "disclosure_scope": plan.disclosure_scope,
    }


def plan_digest(plan: WorkPlan) -> str:
    """Return the exact approval digest for a validated bounded work plan."""
    _validate_plan(plan)
    encoded = json.dumps(
        _canonical_plan(plan),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_approval(plan: WorkPlan, approval: WorkApproval | None) -> None:
    """Validate plan and its exact approval, without authorizing execution.

    Permission lookup, price validation, dispatch, durable reservation, and
    uncertain-outcome recovery are deliberately not implemented here.
    """
    _validate_plan(plan)
    _validate_approval_record(approval)
    checked_approval = cast(WorkApproval, approval)
    if checked_approval.plan_digest != plan_digest(plan):
        _invalid("approval.plan_digest")
