"""Synthetic tests for the bounded model-work approval contract."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from decimal import Decimal, localcontext
import unittest

from benchwarmer.model_work import (
    ModelWorkValidationError,
    WorkApproval,
    WorkItem,
    WorkPlan,
    WorkStage,
    plan_digest,
    validate_approval,
)


def valid_stage(**changes: object) -> WorkStage:
    values: dict[str, object] = {
        "stage_id": "describe-v1",
        "operation": "description",
        "provider": "example-provider",
        "model": "example-model",
        "configuration_digest": "configuration-sha256",
        "input_manifest_digest": "manifest-sha256",
        "max_requests": 3,
        "max_input_tokens": 100,
        "max_output_tokens": 50,
        "max_cost": Decimal("1.25"),
    }
    values.update(changes)
    return WorkStage(**values)  # type: ignore[arg-type]


def valid_plan(**changes: object) -> WorkPlan:
    values: dict[str, object] = {
        "schema_version": 1,
        "items": (WorkItem("conversation-1", "revision-1"),),
        "stages": (valid_stage(),),
        "currency": "USD",
        "max_total_cost": Decimal("2.00"),
        "max_total_requests": 3,
        "max_concurrency": 1,
        "pricing_basis": "price-sheet-2026-09",
        "disclosure_scope": "permission-grant-7",
    }
    values.update(changes)
    return WorkPlan(**values)  # type: ignore[arg-type]


class ModelWorkTests(unittest.TestCase):
    def test_exact_approval_for_valid_frozen_plan(self) -> None:
        plan = valid_plan()
        approval = WorkApproval(plan_digest(plan), "actor-1")

        self.assertIsNone(validate_approval(plan, approval))
        with self.assertRaises(FrozenInstanceError):
            plan.currency = "EUR"  # type: ignore[misc]

    def test_every_consequential_field_changes_digest(self) -> None:
        plan = valid_plan()
        baseline = plan_digest(plan)
        changed_plans = (
            replace(plan, items=(WorkItem("conversation-1", "revision-2"),)),
            replace(plan, stages=(replace(plan.stages[0], stage_id="judge-v1"),)),
            replace(plan, stages=(replace(plan.stages[0], operation="judge"),)),
            replace(
                plan,
                stages=(replace(plan.stages[0], provider="other-provider"),),
            ),
            replace(plan, stages=(replace(plan.stages[0], model="other-model"),)),
            replace(
                plan,
                stages=(
                    replace(plan.stages[0], configuration_digest="configuration-2"),
                ),
            ),
            replace(
                plan,
                stages=(replace(plan.stages[0], input_manifest_digest="manifest-2"),),
            ),
            replace(plan, stages=(replace(plan.stages[0], max_requests=2),)),
            replace(plan, stages=(replace(plan.stages[0], max_input_tokens=101),)),
            replace(plan, stages=(replace(plan.stages[0], max_output_tokens=51),)),
            replace(plan, stages=(replace(plan.stages[0], max_cost=Decimal("1.24")),)),
            replace(plan, currency="EUR"),
            replace(plan, max_total_cost=Decimal("2.01")),
            replace(plan, max_total_requests=4),
            replace(plan, max_concurrency=2),
            replace(plan, pricing_basis="price-sheet-2026-10"),
            replace(plan, disclosure_scope="permission-grant-8"),
        )

        for changed in changed_plans:
            self.assertNotEqual(baseline, plan_digest(changed))

    def test_stale_approval_is_rejected_for_bound_fields(self) -> None:
        plan = valid_plan()
        approval = WorkApproval(plan_digest(plan), "actor-1")
        for changed in (
            replace(plan, items=(WorkItem("conversation-1", "revision-2"),)),
            replace(plan, stages=(replace(plan.stages[0], model="model-2"),)),
            replace(
                plan,
                stages=(replace(plan.stages[0], input_manifest_digest="manifest-2"),),
            ),
            replace(plan, max_total_requests=4),
            replace(plan, pricing_basis="price-sheet-2026-10"),
            replace(plan, disclosure_scope="permission-grant-8"),
        ):
            with self.assertRaises(ModelWorkValidationError) as raised:
                validate_approval(changed, approval)
            self.assertEqual(str(raised.exception), "approval.plan_digest")

    def test_missing_approval_and_empty_approval_fields_are_rejected(self) -> None:
        plan = valid_plan()
        with self.assertRaisesRegex(ModelWorkValidationError, "^approval$"):
            validate_approval(plan, None)
        with self.assertRaisesRegex(ModelWorkValidationError, "^approval.plan_digest$"):
            WorkApproval("", "actor-1")
        with self.assertRaisesRegex(ModelWorkValidationError, "^approval.approved_by$"):
            WorkApproval("digest", "")

    def test_mutable_and_empty_collections_are_rejected(self) -> None:
        with self.assertRaisesRegex(ModelWorkValidationError, "^items$"):
            valid_plan(items=[WorkItem("conversation-1", "revision-1")])
        with self.assertRaisesRegex(ModelWorkValidationError, "^stages$"):
            valid_plan(stages=[valid_stage()])
        with self.assertRaisesRegex(ModelWorkValidationError, "^items$"):
            valid_plan(items=())
        with self.assertRaisesRegex(ModelWorkValidationError, "^stages$"):
            valid_plan(stages=())

    def test_malformed_primitives_and_identities_are_rejected(self) -> None:
        cases = (
            (lambda: WorkItem("", "revision"), "input_id"),
            (lambda: WorkItem("input", ""), "input_revision"),
            (lambda: valid_stage(max_requests=True), "max_requests"),
            (lambda: valid_stage(max_input_tokens=True), "max_input_tokens"),
            (lambda: valid_stage(max_output_tokens=-1), "max_output_tokens"),
            (lambda: valid_stage(max_cost=1.0), "max_cost"),
            (lambda: valid_stage(operation="other"), "operation"),
            (lambda: valid_plan(schema_version=True), "schema_version"),
            (lambda: valid_plan(schema_version=2), "schema_version"),
            (lambda: valid_plan(currency="usd"), "currency"),
            (lambda: valid_plan(max_concurrency=0), "max_concurrency"),
        )
        for construct, field in cases:
            with (
                self.subTest(field=field),
                self.assertRaises(ModelWorkValidationError) as raised,
            ):
                construct()
            self.assertEqual(str(raised.exception), field)

    def test_contract_type_subclasses_are_rejected(self) -> None:
        class WorkItemSubtype(WorkItem):
            pass

        class WorkStageSubtype(WorkStage):
            pass

        class WorkPlanSubtype(WorkPlan):
            pass

        class WorkApprovalSubtype(WorkApproval):
            pass

        cases = (
            (lambda: WorkItemSubtype("input", "revision"), "items"),
            (
                lambda: WorkStageSubtype(
                    "stage",
                    "description",
                    "provider",
                    "model",
                    "configuration",
                    "manifest",
                    1,
                    0,
                    0,
                    Decimal("0"),
                ),
                "stages",
            ),
            (
                lambda: WorkPlanSubtype(
                    1,
                    (WorkItem("input", "revision"),),
                    (valid_stage(),),
                    "USD",
                    Decimal("1"),
                    3,
                    1,
                    "pricing",
                    "disclosure",
                ),
                "plan",
            ),
            (lambda: WorkApprovalSubtype("digest", "actor"), "approval"),
        )
        for construct, field in cases:
            with (
                self.subTest(field=field),
                self.assertRaisesRegex(ModelWorkValidationError, rf"^{field}$"),
            ):
                construct()

    def test_duplicate_items_and_stages_are_rejected(self) -> None:
        item = WorkItem("conversation-1", "revision-1")
        with self.assertRaisesRegex(ModelWorkValidationError, "^items$"):
            valid_plan(items=(item, item))
        stage = valid_stage()
        with self.assertRaisesRegex(ModelWorkValidationError, "^stages$"):
            valid_plan(stages=(stage, stage), max_total_requests=6)

    def test_request_and_cost_limits_allow_exact_exhaustion_only(self) -> None:
        first = valid_stage(stage_id="first", max_requests=2, max_cost=Decimal("0.10"))
        second = valid_stage(
            stage_id="second", max_requests=3, max_cost=Decimal("0.20")
        )
        exact = valid_plan(
            stages=(first, second),
            max_total_requests=5,
            max_total_cost=Decimal("0.30"),
            max_concurrency=5,
        )
        self.assertEqual(plan_digest(exact), plan_digest(exact))
        with self.assertRaisesRegex(ModelWorkValidationError, "^max_total_requests$"):
            replace(exact, max_total_requests=4)
        with self.assertRaisesRegex(ModelWorkValidationError, "^max_concurrency$"):
            replace(exact, max_concurrency=6)
        with self.assertRaisesRegex(ModelWorkValidationError, "^max_total_cost$"):
            replace(exact, max_total_cost=Decimal("0.299"))

    def test_decimal_canonicalization_is_context_independent(self) -> None:
        precise_stage = valid_stage(
            max_cost=Decimal("123456789012345678901234567890.1200")
        )
        precise_plan = valid_plan(
            stages=(precise_stage,),
            max_total_cost=Decimal("123456789012345678901234567890.12000"),
        )
        equivalent = valid_plan(
            stages=(
                replace(
                    precise_stage, max_cost=Decimal("123456789012345678901234567890.12")
                ),
            ),
            max_total_cost=Decimal("123456789012345678901234567890.12"),
        )
        with localcontext() as context:
            context.prec = 4
            low_precision_digest = plan_digest(precise_plan)
        with localcontext() as context:
            context.prec = 80
            high_precision_digest = plan_digest(precise_plan)
        self.assertEqual(low_precision_digest, high_precision_digest)
        self.assertEqual(plan_digest(precise_plan), plan_digest(equivalent))

    def test_decimal_representation_limits_are_bounded(self) -> None:
        accepted = valid_stage(max_cost=Decimal("1E+1000"))
        self.assertEqual(accepted.max_cost, Decimal("1E+1000"))
        for value in (
            Decimal("1E+1001"),
            Decimal("1E-1001"),
            Decimal("1" * 1001),
        ):
            with (
                self.subTest(value=value),
                self.assertRaisesRegex(ModelWorkValidationError, "^max_cost$"),
            ):
                valid_stage(max_cost=value)

    def test_unpaired_surrogate_is_ascii_escaped_in_canonical_digest(self) -> None:
        plan = valid_plan(stages=(replace(valid_stage(), model="\ud800"),))
        self.assertEqual(plan_digest(plan), plan_digest(plan))
        self.assertEqual(len(plan_digest(plan)), 64)

    def test_zero_cost_work_remains_bounded_and_requires_approval(self) -> None:
        plan = valid_plan(
            stages=(valid_stage(max_cost=Decimal("0E-999")),),
            max_total_cost=Decimal("0.000"),
        )
        with self.assertRaisesRegex(ModelWorkValidationError, "^approval$"):
            validate_approval(plan, None)
        validate_approval(plan, WorkApproval(plan_digest(plan), "actor-1"))

    def test_error_messages_do_not_echo_supplied_values(self) -> None:
        sentinel = "private-sentinel-content"
        with self.assertRaises(ModelWorkValidationError) as raised:
            WorkItem(sentinel, "")
        self.assertNotIn(sentinel, str(raised.exception))


if __name__ == "__main__":
    unittest.main()
