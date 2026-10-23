# Run approved model work with durable limits and recovery

Status: In progress. The first slice (plan preview, digest-bound approval, one subprocess per plan, cancellation, interrupted-not-rerun) is implemented for `propose-bundles` per [ADR 0006](../../../docs/decisions/0006-app-started-model-work.md); reservation, retries, and outcome-unknown recovery remain pending.

## Purpose

Turn the existing pure approval contract into an execution service before dispatching enrichment, embedding, or judge requests.

## Dependencies and order

Blocked on [conversation browsing](../conversation-library/README.md). The immutable approval validator is implemented; it does not provide reservation, scheduling, or recovery.

## Acceptance criteria

No request starts without valid disclosure permission and exact bounded approval. Durable reservation, cancellation, bounded retries, and uncertain-outcome recovery prevent silent repeated paid work; changed plans invalidate approval.

## Work

- [ ] Run approved model work with durable limits and recovery
  - [x] Preview a frozen plan and approve it by digest from the Bundles page;
    run the proposer as one subprocess per plan; cancel; mark plans left
    running at startup as interrupted (`model_work_plans`, migration 0007)
  - [x] Pick the model from the providers whose keys the server holds: the
    harness merges each provider's own list, models.dev, and the pinned pi-ai
    catalog (`list-models --json`, `GET /model-work/models`, cached ten
    minutes); the thinking selector follows the chosen model; a model outside
    the pinned catalog runs with its nearest sibling's settings and records the
    price estimate's source
  - [ ] Durable budget reservation once a pricing source exists for the plan
  - [ ] Bounded retries and outcome-unknown recovery
  - [ ] Offer other workflows (judges, anonymizer) once their limits are defined
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
