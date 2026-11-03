# Reconcile usage and add detailed economics reports

Status: Planned. Implementation and delivery are pending unless a supporting record explicitly says otherwise.

## Purpose

Explain usage and economics without inflating totals from overlapping source observations.

## Dependencies and order

Blocked on [a second source](../additional-sources/README.md) for cross-source
reconciliation and [browsing](../conversation-library/README.md) for detailed
reporting. The earlier [history and cost dashboards](../history-and-cost-dashboards/README.md)
show basic sourced activity and time series without claiming unreconciled totals.
Imported usage and cost provenance still ship with the library.

## Acceptance criteria

Related observations stay retained and their overlap decisions are inspectable. Actual charges, estimates, subscriptions, and quotas remain distinct; unmatched data and coverage gaps are shown rather than silently summed.

## Work

- [ ] Reconcile overlapping harness/provider observations
  - Dependencies: [Add a second source adapter](../additional-sources/README.md)
  - Contract: [ADR 0007](../../../docs/decisions/0007-source-evidence-and-reconciliation.md).
    Retain both observations and explicit evidence links. Verified native/provider
    identifiers may support joins; similarity-only matches stay candidates.
  - Verify synthetic fixtures for colliding IDs across source scopes, protocol IDs
    versus provider generation IDs, missing IDs, contradictory observations, and
    false matches sharing model/timestamp/token counts. No destructive merge.
  - Aggregate request and session scopes without counting the same usage twice;
    reasoning/cache subsets must not be added to their containing totals.
  - Test unknown versus confirmed zero, estimates versus charges, balance versus
    spend history, and timestamped price evidence versus current catalog prices.

- [ ] Expose gaps and reconciliation decisions in API and UI
  - Dependencies: [Reconcile overlapping harness/provider observations](../usage-reconciliation/README.md)

- [ ] Add detailed usage and economics reporting
  - Dependencies: [Browse conversations and search their text and metadata](../conversation-library/README.md), [Expose gaps and reconciliation decisions in API and UI](../usage-reconciliation/README.md)
  - Priority: follows useful conversation discovery; never a library gate

## Verification

Before implementing a broad step, specify its files, fixtures, and focused
checks here. Follow [repository validation](../../../AGENTS.md) and record actual
results at handoff. This record currently defines planned work.

## Supporting material

- [Current priorities](../../TODO.md)
- [Conversation workflow](../../../docs/conversation-library.md)
- [Experiment semantics](../../../docs/experiments.md)
- [Source evidence and reconciliation](../../../docs/decisions/0007-source-evidence-and-reconciliation.md)
