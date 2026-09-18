# Collect conversations from other machines

Status: Planned. Implementation and delivery are pending unless a supporting record explicitly says otherwise.

## Purpose

Deliver enrolled, read-only manual push collection before optional scheduling. The central host must not assume histories all live locally.

## Dependencies and order

Blocked on [Hermes import](../hermes-import/README.md) and [the application foundation](../application-foundation/README.md). Operational rollout also requires [private deployment](../private-deployment/README.md).

## Acceptance criteria

Enrollment, allowlists, bounded spooling and backfill, offline catch-up, durable receipts, duplicate delivery, and revocation follow [ADR 0005](../../../docs/decisions/0005-cross-machine-collection.md). Add scheduling only after the manual path is reliable.

## Work

- [ ] Collect conversations from other machines
  - Dependencies: [Plan collection from the user's other machines](../../../docs/decisions/0005-cross-machine-collection.md) (already recorded), [Add shared conversation records and synthetic source examples](../conversation-contracts/README.md) (already recorded), [Import Hermes conversations reliably](../hermes-import/README.md), [Document development and final integration](../application-foundation/README.md)
  - Scope: manual push collector first, versioned enrollment and upload protocol,
    source allowlists, bounded private spool/backfill, durable acknowledgment,
    duplicate delivery and revocation tests; add optional `launchd` scheduling
    only after the manual path is reliable
  - Gate: exact files, limits, transport, packaging, and tests must follow
    [ADR 0005](../../../docs/decisions/0005-cross-machine-collection.md); operational rollout
    also requires [Implement and validate private deployment](../private-deployment/README.md)

## Verification

Before implementing a broad step, specify its files, fixtures, and focused
checks here. Follow [repository validation](../../../AGENTS.md) and record actual
results at handoff. This record currently defines planned work.

## Supporting material

- [Current priorities](../../TODO.md)
- [Conversation workflow](../../../docs/conversation-library.md)
- [Experiment semantics](../../../docs/experiments.md)
