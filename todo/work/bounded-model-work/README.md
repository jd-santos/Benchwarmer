# Run approved model work with durable limits and recovery

Status: Planned. Implementation and delivery are pending unless a supporting record explicitly says otherwise.

## Purpose

Turn the existing pure approval contract into an execution service before dispatching enrichment, embedding, or judge requests.

## Dependencies and order

Blocked on [conversation browsing](../conversation-library/README.md). The immutable approval validator is implemented; it does not provide reservation, scheduling, or recovery.

## Acceptance criteria

No request starts without valid disclosure permission and exact bounded approval. Durable reservation, cancellation, bounded retries, and uncertain-outcome recovery prevent silent repeated paid work; changed plans invalidate approval.

## Work

- [ ] Run approved model work with durable limits and recovery
  - Dependencies: [Add bounded model-work plans and exact approval validation](../conversation-contracts/README.md) (already recorded), [Browse conversations and search their text and metadata](../conversation-library/README.md)
  - Scope: preview/approval UI, disclosure checks, durable request/cost reservations,
    cancellation, bounded retries and outcome-unknown recovery
  - Gate: no model stage dispatch before its durable safety tests pass

## Verification

Before implementing a broad step, specify its files, fixtures, and focused
checks here. Follow [repository validation](../../../AGENTS.md) and record actual
results at handoff. This record currently defines planned work.

## Supporting material

- [Current priorities](../../TODO.md)
- [Conversation workflow](../../../docs/conversation-library.md)
- [Experiment semantics](../../../docs/experiments.md)
