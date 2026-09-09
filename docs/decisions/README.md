# Decision records

Decision work is split into independent proposal files so agents can research in
parallel without editing the same index or task queue.

## Ownership

- A decision worker edits only the exact record assigned in `docs/TODO.md`.
- Decision workers do not edit `docs/TODO.md`, `docs/decisions.md`, or another
  worker's record.
- The coordinating agent reviews completed records together, resolves conflicts,
  updates [../decisions.md](../decisions.md), and records task transitions in
  [../TODO.md](../TODO.md) in one integration change.
- A proposal is not an accepted project decision until the coordinating task says
  so. Implementation must depend on that coordinating task when it needs several
  proposals to agree.

## Required record shape

```markdown
# ADR NNNN: Title

- Status: Proposed
- Task: TASK-ID
- Date: YYYY-MM-DD

## Context and evidence

Observed facts, source links, commands, and explicitly unknown information.

## Decision

The proposed choice and its scope.

## Alternatives considered

Options considered and why they were not selected.

## Consequences

Operational, security, migration, testing, and maintenance effects.

## Unresolved questions

Anything the coordinating agent must reconcile before acceptance.

## Verification

Commands or target-host checks that validate the proposal.
```

Use stable numbered filenames. The initial records are:

- [0001 — Application foundation](0001-application-foundation.md) — Accepted
- [0002 — Private data and recovery](0002-data-recovery.md) — Accepted
- [0003 — Private serving and supervision](0003-serving-supervision.md) — Accepted
- `0004-first-import-adapter.md` — assigned to `SRC-002`, not yet written

When a decision is superseded, preserve the old record and link the replacement.
Do not rewrite prior rationale as though the earlier decision never existed.

Private paths, credentials, prompt text, session content, and raw provider
responses do not belong in decision records.
