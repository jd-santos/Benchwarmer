# Design test-plan authoring and applied-judge preview

Type: Prototype, human in the loop\
Status: Resolved\
Claim: None\
Parent: [Design the evidence-to-evaluation workbench UI](../README.md)\
Blocked by: [Define evaluation-project navigation and artifact relationships](project-navigation.md) and [Design bundle-to-task promotion and readiness review](task-promotion.md)\
Blocks: [Design run monitoring, interruption, and recovery](run-monitoring.md), [Design trial, judgment, and disagreement review](judgment-review.md), and [Define responsive transformations and the keyboard workflow](responsive-and-keyboard-workflow.md)

## Question

How should the user compose, inspect, validate, version, and approve a test plan
from task families or tags, frozen task versions, candidate configurations,
repetitions, applied judges, execution policies, and budget?

Prototype selection and grouping, configuration comparison, unsupported
capabilities, judge criteria and evidence access, deterministic checks, requested
versus expected effective settings, estimate ranges and coverage gaps, candidate
versus judge overhead, disclosure permission, retries, cancellation, and exact
approval scope. Make it possible to understand how every judge will act on every
applicable task before approval, without pretending a changed multi-variable
configuration isolates one causal factor.

## Resolution

Decided with the user on 2026-10-15.

The user selects tasks (by family, tag, or version) and configurations. A task ×
configuration matrix shows repetitions, the applied judges per cell,
unsupported cells, and an estimate range. Approval shows the exact scope and
budget, with candidate and judge cost shown separately.
