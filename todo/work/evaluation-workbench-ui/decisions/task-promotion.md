# Design bundle-to-task promotion and readiness review

Type: Prototype, human in the loop\
Status: Resolved\
Claim: None\
Parent: [Design the evidence-to-evaluation workbench UI](../README.md)\
Blocked by: [Design evidence selection and bundle assembly](evidence-selection-and-bundles.md)\
Blocks: [Design test-plan authoring and applied-judge preview](test-plan-authoring.md)

## Question

How should a reviewed bundle become a task draft and then a versioned runnable
task without implying that every useful bundle can be reconstructed?

Prototype a readiness review that separates candidate-visible starting context
from judge-only historical evidence and exposes reconstruction level, missing
state, required capabilities, fixture needs, fixed follow-ups, assertions,
lineage, partition, answer-leakage risks, and unresolved human review. Decide how
narrowing the task, preparing a new fixture, declaring analysis-only status, and
creating a new version affect the visible relationship to the motivating bundle.

## Resolution

Decided with the user on 2026-10-15.

A guided wizard walks from bundle to published task, but each step saves a
reversible stage: bundle, then task draft, then immutable task version. The user
can leave and resume, or open any stage directly. This keeps the starting
commitment to explicit, reversible stages. The readiness step separates
candidate-visible context from judge-only evidence and flags leakage, missing
state, and fixture needs. Bundles can be marked analysis-only and skip the wizard.
