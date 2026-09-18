# Decision records

Accepted decisions retain stable numbered ADR filenames. Task tracking uses
human-readable names in [the workbench](../../todo/README.md); ADR numbers are
document identifiers, not task codes.

## Ownership and review

A decision worker edits its assigned record and work README. One integrator
reconciles shared decisions and the priority index. Use separate worktrees for
concurrent writers. A proposal becomes accepted only after review; implementation
must wait when its required choices remain unresolved.

## Record shape

```markdown
# ADR NNNN: Title

- Status: Proposed
- Work: Readable task name or link to its work README
- Date: YYYY-MM-DD

## Context and evidence

Observed facts, source links, commands, and explicitly unknown information.

## Decision

The proposed choice and its scope.

## Alternatives considered

Options considered and why they were not selected.

## Consequences

Operational, migration, testing, and maintenance effects.

## Unresolved questions

Choices that must be reconciled before acceptance.

## Verification

Commands or target-host checks that validate the proposal.
```

## Accepted records

- [Application foundation](0001-application-foundation.md)
- [Private data and recovery](0002-data-recovery.md)
- [Private serving and supervision](0003-serving-supervision.md)
- [First import adapter](0004-first-import-adapter.md)
- [Cross-machine collection](0005-cross-machine-collection.md)

When a decision is superseded, preserve its rationale and link the replacement.
Keep private paths, credentials, prompts, sessions, and raw provider responses
out of decision records.
