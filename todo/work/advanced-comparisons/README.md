# Add controlled comparisons and adaptive follow-ups

Status: Planned. Implementation and delivery are pending unless a supporting record explicitly says otherwise.

## Purpose

Extend proven fixed experiments with explicit configuration controls and later adaptive user continuation.

## Dependencies and order

Blocked on [judged experiments](../judged-experiments/README.md). Choose the controlled-comparison and simulator policies before implementation.

## Acceptance criteria

Controlled runs show overrides and remaining differences. Adaptive results disclose simulator instructions, allowed knowledge, cost, and reliability, and never claim exact historical replay.

## Work

- [ ] Add controlled comparisons with explicit overrides
  - Dependencies: [Compare criterion-level quality and economics per trial](../judged-experiments/README.md)
  - Promotion requirement: the coordinator adds a controlled-comparison
    decision record before implementation

- [ ] Add later adaptive user continuation
  - Dependencies: [Compare criterion-level quality and economics per trial](../judged-experiments/README.md), user-approved simulator policy
  - Scope: intent-preserving follow-ups, separate simulator provenance/cost,
    allowed-knowledge and leakage checks; never label as exact replay

## Verification

Before implementing a broad step, specify its files, fixtures, and focused
checks here. Follow [repository validation](../../../AGENTS.md) and record actual
results at handoff. This record currently defines planned work.

## Supporting material

- [Current priorities](../../TODO.md)
- [Conversation workflow](../../../docs/conversation-library.md)
- [Experiment semantics](../../../docs/experiments.md)
