# Browse, search, and annotate conversations

Status: Planned. Implementation and delivery are pending unless a supporting record explicitly says otherwise.

## Purpose

Make the imported library useful immediately: find work, follow its actual branch, and record human observations before adding automated analysis.

## Dependencies and order

Blocked on [Hermes import](../hermes-import/README.md). Ratings and corrections move alongside the first browsing release so there is useful human evidence for later enrichment and judge calibration.

## Acceptance criteria

Search opens the matching evidence, branches and continuations stay distinct, and ratings, labels, notes, and their revisions survive restart. The main reading path works on desktop and mobile without requiring cost charts or inference.

## Work

- [ ] Browse conversations and search their text and metadata
  - Dependencies: [Import Hermes conversations reliably](../hermes-import/README.md)
  - Scope: readable transcripts, branches/continuations, source freshness,
    coverage, filters and evidence-linked keyword search; usage/cost as metadata,
    no chart dependency

- [ ] Add ratings, labels, notes, and annotation revision history
  - Dependencies: [Browse conversations and search their text and metadata](../conversation-library/README.md)

## Verification

Before implementing a broad step, specify its files, fixtures, and focused
checks here. Follow [repository validation](../../../AGENTS.md) and record actual
results at handoff. This record currently defines planned work.

## Supporting material

- [Current priorities](../../TODO.md)
- [Conversation workflow](../../../docs/conversation-library.md)
- [Experiment semantics](../../../docs/experiments.md)
