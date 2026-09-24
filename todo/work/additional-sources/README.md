# Add the other conversation sources

Status: Planned. Implementation and delivery are pending unless a supporting record explicitly says otherwise.

## Purpose

Bring Pi, Codex, Hermes, and available Claude Cowork history from the desktop
app into one library while testing that shared records preserve their different
source structures. Standard Claude chat is a desirable later source if
accessible. Claude is gradually unifying chat and Cowork in its UI, so source
research must identify the actual session type rather than rely on a mode label.

## Dependencies and order

Blocked on [Hermes import](../hermes-import/README.md) and [verified additional-source research](../additional-source-research/README.md). Choose the second source from actual available history and refreshed evidence before naming exact implementation files.

## Acceptance criteria

Each added source adapter preserves the native evidence it can access, identity,
branches or continuations where present, and explicit capture gaps. Idempotent
updates and reconciliation pass source-specific tests without assuming import
implies execution support. Unavailable Claude Cowork fields or export
paths remain documented gaps rather than invented parity.

## Work

- [ ] Add a second source adapter
  - Dependencies: [Import Hermes conversations reliably](../hermes-import/README.md), [Verify additional conversation sources](../additional-source-research/README.md)
  - Promotion requirement: the coordinator names the exact second-source work and required inspection report before implementation

- [ ] Add the remaining Pi/Codex source adapter
  - Dependencies: [Add a second source adapter](../additional-sources/README.md)
  - Gate: refresh source evidence and name exact adapter tasks before launch

- [ ] Investigate and add Claude Cowork history where access is feasible
  - Dependencies: [Inspect Claude Desktop and Claude Code evidence](../additional-source-research/README.md)
  - Scope: preserve native content and available settings, usage, and cost with
    provenance; report inaccessible fields explicitly
  - Gate: verify the actual source interface before committing to an adapter

## Verification

Before implementing a broad step, specify its files, fixtures, and focused
checks here. Follow [repository validation](../../../AGENTS.md) and record actual
results at handoff. This record currently defines planned work.

## Supporting material

- [Current priorities](../../TODO.md)
- [Conversation workflow](../../../docs/conversation-library.md)
- [Experiment semantics](../../../docs/experiments.md)
- [Claude Cowork and chat are one Claude](https://support.claude.com/en/articles/16761823-claude-cowork-and-chat-are-one-claude)
