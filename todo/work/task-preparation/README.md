# Turn selected evidence into runnable tasks

Status: Planned. Implementation and delivery are pending unless a supporting record explicitly says otherwise.

## Purpose

Prepare representative work from successes, failures, recoveries, and ambiguous outcomes for comparing configurations.

## Dependencies and order

Blocked on [frozen datasets](../collections-and-datasets/README.md) and [evidence bundles](../evidence-bundles/README.md). Manual task drafting does not depend on automated clustering; model-assisted drafting also needs bounded execution.

## Acceptance criteria

A reviewed task version declares intent, starting context, capability and fixture needs, reconstruction gaps, and criterion-level assertions. Historical answers and later workspace state remain outside candidate inputs; correlated source lineage is retained.

## Work

- [ ] Prepare meaningful task units from frozen datasets
  - Dependencies: [Add projects, live collections and frozen datasets](../collections-and-datasets/README.md)
  - Scope: one-to-few-exchange units, sufficient context, segmentation provenance,
    correlated source lineage, reconstruction gaps and leakage checks
  - Promotion requirement: the coordinator names the first task-family and
    reconstruction decision records before implementation

  - [ ] Give candidate inputs and judge-only historical evidence distinct typed roles; validate that references cannot leak the original answer or later discoveries into a rerun.
  - [ ] Derive reviewable assertions about acceptable behavior, rather than requiring the historical answer or incidental wording. Keep source evidence and criterion revisions attached.
  - [ ] Record analysis-only bundles when starting state is missing; do not silently convert them into runnable tasks. Retain correlated conversation and branch lineage.

## Verification

Before implementing a broad step, specify its files, fixtures, and focused
checks here. Follow [repository validation](../../../AGENTS.md) and record actual
results at handoff. This record currently defines planned work.

## Supporting material

- [Current priorities](../../TODO.md)
- [Conversation workflow](../../../docs/conversation-library.md)
- [Experiment semantics](../../../docs/experiments.md)
- [Evidence bundles and pattern discovery](../../../docs/evidence-bundles.md)
