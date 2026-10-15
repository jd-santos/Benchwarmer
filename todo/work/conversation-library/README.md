# Browse, search, and annotate conversations

Status: Planned. Implementation and delivery are pending unless a supporting record explicitly says otherwise.

## Purpose

Make the imported library useful immediately: find work, follow its actual branch, and record human observations before adding automated analysis. This browsing path is the foundation for the [history and cost dashboards](../history-and-cost-dashboards/README.md).

## Dependencies and order

Blocked on [Hermes import](../hermes-import/README.md). Ratings and corrections move alongside the first browsing release so there is useful human evidence for later enrichment and judge calibration.

## Acceptance criteria

Search opens the matching evidence, branches and continuations stay distinct, and ratings, labels, notes, and their revisions survive restart. The main reading path works on desktop and mobile. Basic charting follows as a separate slice so browsing does not wait for a reporting implementation.

## Work

- [ ] Browse conversations and search their text and metadata
  - Dependencies: [Import Hermes conversations reliably](../hermes-import/README.md)
  - Scope: readable transcripts, branches/continuations, source freshness,
    coverage, filters and evidence-linked keyword search; usage/cost as metadata,
    no chart dependency
  - [x] List, filter, and keyword-search latest revisions; read a conversation
    with branch paths, revision history, and two-way continuation links
    (`GET /api/v1/conversations`, `GET /api/v1/conversations/{id}`) on
    `task/conversation-browsing`. Verified with synthetic imports in
    `tests/api/test_conversation_api.py` and all repository checks.
  - [ ] Replace the per-request search scan with an SQLite FTS5 index before
    real library volumes
  - [ ] Conversation list and transcript screens

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
