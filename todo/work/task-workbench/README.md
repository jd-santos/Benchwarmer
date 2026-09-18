# Migrate task tracking and add evidence-bundling recommendations

Status: Ready for merge. Delivery is recorded by the commit containing this
closeout; no merge or release is claimed.

Ownership: Coordinating session, documentation migration only, on the existing
`task/conversation-library` branch. No other active Benchwarmer task or sibling
worktree was observed when work began. Ownership text is not a lock.

## Purpose

Adopt the root todo-manager workbench, replace opaque task labels with readable
names, preserve unfinished work, and add the researched evidence-bundle concepts
in the order that best supports a useful conversation library.

## Acceptance criteria

One P1–P5 index owns live priorities. Every prior unfinished task and its useful
dependencies, outputs, acceptance, and checks has a readable work-record home.
Completed history is recoverable, old navigation resolves, and no obsolete plan
is presented as current implementation work. The recommendations are planned
capabilities rather than claims that code exists.

## Work

- [x] Inventory the legacy queue, worktrees, available active tasks, and Git status.
- [x] Verify that all 25 checked legacy entries and their unique notes are committed before retiring the Done ledger.
- [x] Preserve all 40 unfinished task identities across descriptive work records, with one detailed checklist per scope.
- [x] Create the P1–P5 index, human-facing introduction, and history entry point; keep redirects for legacy paths.
- [x] Retain the completed contract design and superseded handoff as historical evidence, with current navigation.
- [x] Add evidence references, manual bundles, selective inspection, versioned patterns, and task/assertion promotion to maintained design and linked work records.
- [x] Reconcile agent instructions, roadmap, planning references, and task-code links.
- [x] Verify task preservation, Markdown links and anchors, priority structure, and whitespace against the final diff.

## Priority decisions

There is no emergency work. P2 follows the shortest useful path: finish the
foundation, import Hermes, browse/search and record human feedback, then review
evidence bundles. Human review moves alongside browsing instead of waiting for
automated analysis. Bundle contract design can start with synthetic data, while
its pilot waits for real browsing.

P3 contains required operational collection, datasets/private access, bounded
model execution, enrichment, remaining sources, and safe judged experiments.
Manual datasets do not depend on inference; manually drafted tasks do not depend
on automated grouping. Existing deployment and execution gates remain in force.

P4 contains patterns at scale, semantic search, aggregate usage reporting,
external model evidence, controlled/adaptive comparisons, and public reports.
They are retained but do not postpone the useful library. Imported usage and
cost provenance still belong in the first importer. P5 is empty rather than
filled with invented polish tasks.

## Preservation and delivery

The original queue exactly matched commit
`832c5bb4fdcacc73bf970ded0de56286bf6259c2` before migration. Recover it with
`git show 832c5bb4fdcacc73bf970ded0de56286bf6259c2:docs/TODO.md`.
The three importer substeps retain the original first-importer milestone scope;
its parent is represented by the work record and index entry rather than a
duplicate execution checklist. All other unfinished entries remain checklist
steps. Historical checked entries remain in Git; they are not reopened as new
work or copied into another completion ledger.

Legacy queue and moved-plan files become redirects. No file deletions, code
changes, model dispatch, or deployment are part of this migration.

## Validation

Migration checks passed for all 40 unfinished task identities, the ordered P1–P5
headings, absence of obsolete task codes, and 441 local Markdown links including
heading anchors. The original 25 checked entries were verified recoverable from
the committed baseline. `git diff --check` passed. The final diff contains only
Markdown, and moved plans have working redirects.

No application tests were run because this change only updates documentation and
task tracking. Future implementation checks remain unchecked in their own work
records. No model calls, releases, or deployment were performed.

## Supporting material

- [Priority index](../../TODO.md)
- [Workbench introduction](../../README.md)
- [History](../../DONE.md)
- [Maintained evidence-bundle design](../../../docs/evidence-bundles.md)
- [Delivery roadmap](../../../docs/roadmap.md)
