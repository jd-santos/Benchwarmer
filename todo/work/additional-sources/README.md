# Add the other conversation sources

Status: Planned. Implementation and delivery are pending unless a supporting record explicitly says otherwise.

## Purpose

Bring Pi, Codex, and Hermes into one library while testing that shared records preserve their different source structures.

## Dependencies and order

Blocked on [Hermes import](../hermes-import/README.md) and [verified additional-source research](../additional-source-research/README.md). Choose the second source from actual available history and refreshed evidence before naming exact implementation files.

## Acceptance criteria

Both remaining source adapters preserve native snapshots, identity, branches or continuations, and capture gaps. Idempotent updates and reconciliation pass source-specific tests without assuming import implies execution support.

## Work

- [ ] Add a second source adapter
  - Dependencies: [Import Hermes conversations reliably](../hermes-import/README.md), [Verify additional conversation sources](../additional-source-research/README.md)
  - Promotion requirement: the coordinator names the exact second-source work and required inspection report before implementation

- [ ] Add the remaining Pi/Codex/Hermes source adapter
  - Dependencies: [Add a second source adapter](../additional-sources/README.md)
  - Gate: refresh source evidence and name exact adapter tasks before launch

## Verification

Before implementing a broad step, specify its files, fixtures, and focused
checks here. Follow [repository validation](../../../AGENTS.md) and record actual
results at handoff. This record currently defines planned work.

## Supporting material

- [Current priorities](../../TODO.md)
- [Conversation workflow](../../../docs/conversation-library.md)
- [Experiment semantics](../../../docs/experiments.md)
