# Add trusted evaluation evidence and model views

Status: Planned. Implementation and delivery are pending unless a supporting record explicitly says otherwise.

## Purpose

Place trusted published evaluations beside local experience without treating unlike scores as a common ranking.

## Dependencies and order

Blocked on [conversation browsing and annotations](../conversation-library/README.md). External evidence precedes its model views; this work does not block the library or private experiments.

## Acceptance criteria

Evidence keeps publisher, dates, methodology, immutable revisions, and known configuration. Model identity uncertainty remains visible, and source-specific fetch permissions are verified before automation.

## Work

- [ ] Add trusted external evidence with immutable revisions
  - Dependencies: [Browse conversations and search their text and metadata](../conversation-library/README.md), [Add ratings, labels, notes, and annotation revision history](../conversation-library/README.md)
  - Priority: deferred behind conversation discovery and reusable datasets

- [ ] Add model/configuration evidence views
  - Dependencies: [Browse conversations and search their text and metadata](../conversation-library/README.md), [Add trusted external evidence with immutable revisions](../external-evidence/README.md)

## Verification

Before implementing a broad step, specify its files, fixtures, and focused
checks here. Follow [repository validation](../../../AGENTS.md) and record actual
results at handoff. This record currently defines planned work.

## Supporting material

- [Current priorities](../../TODO.md)
- [Conversation workflow](../../../docs/conversation-library.md)
- [Experiment semantics](../../../docs/experiments.md)
