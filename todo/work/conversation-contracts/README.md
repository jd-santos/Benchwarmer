# Conversation and approval contracts

Status: Retained record. Implementation exists in Git; no release or merge claim is made here.

## Purpose and evidence

The pure conversation and model-work approval contracts establish source identity,
branches, tool linkage, versioned metadata, and exact bounded approval validation.
Implementation is recorded in commits `d434703` and `d6dae11`, verified in local
history during the workbench migration. These contracts do not implement import,
inference, durable reservations, or a scheduler.

## Supporting material

- [Contract design](design.md), retained for schema rationale and validation boundaries.
- [Conversation validation](../../../src/benchwarmer/conversations.py)
- [Model-work validation](../../../src/benchwarmer/model_work.py)
- [Historical handoff](../../../docs/plans/2026-09-15-conversation-handoff.md), retained only for the original tooling and review blockers; not a resume plan.
- [Current priorities](../../TODO.md)
