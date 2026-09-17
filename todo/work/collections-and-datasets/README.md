# Save collections and freeze reusable datasets

Status: Planned. Implementation and delivery are pending unless a supporting record explicitly says otherwise.

## Purpose

Make selected work reusable from the UI, scripts, and notebooks before requiring model enrichment or trial execution.

## Dependencies and order

Blocked on [conversation browsing](../conversation-library/README.md). Whole-conversation selection can ship first; bundle selection depends on [evidence bundles](../evidence-bundles/README.md).

## Acceptance criteria

Live queries and frozen membership remain distinct. Exports pin source, enrichment, bundle, and selection revisions where applicable, disclose exclusions and coverage, and never trigger inference or imply public sanitization.

## Work

- [ ] Add projects, live collections and frozen datasets
  - Dependencies: [Browse conversations and search their text and metadata](../conversation-library/README.md), [Add shared conversation records and synthetic source examples](../conversation-contracts/README.md) (already recorded)
  - Scope: saved queries and exact pinned membership/source/enrichment revisions;
    collection growth never triggers model work

  - [ ] Pin bundle and pattern revisions when selected; preserve selection rationale, exclusions, coverage, and source-family counts. Show how the selected sample differs from the available library.

- [ ] Provide private query and dataset export access
  - Dependencies: [Add projects, live collections and frozen datasets](../collections-and-datasets/README.md)
  - Scope: local read/query API and private export for scripts/notebooks; no
    dependency on UI automation or unstable internal database tables

## Verification

Before implementing a broad step, specify its files, fixtures, and focused
checks here. Follow [repository validation](../../../AGENTS.md) and record actual
results at handoff. This record currently defines planned work.

## Supporting material

- [Current priorities](../../TODO.md)
- [Conversation workflow](../../../docs/conversation-library.md)
- [Experiment semantics](../../../docs/experiments.md)
