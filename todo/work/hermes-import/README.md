# Import Hermes conversations reliably

Status: Planned. Implementation and delivery are pending unless a supporting record explicitly says otherwise.

## Purpose

Make the first real histories available for browsing while retaining private native evidence and explicit capture gaps.

## Dependencies and order

Blocked on [the application foundation](../application-foundation/README.md). The shared conversation contract and first-adapter decision are already implemented or accepted. This record owns the complete first-importer milestone.

## Acceptance criteria

Initial, unchanged, appended, interrupted, edited, and source-deleted histories import without duplicating or erasing retained evidence. Source versions and unsupported schemas remain visible; public fixtures are synthetic.

## Work

- [ ] Read supported Hermes histories without modifying them
  - Dependencies: [Select the first import adapter](../../../docs/decisions/0004-first-import-adapter.md) (already recorded), [Expose fixture-backed source status](../application-foundation/README.md), [Document development and final integration](../application-foundation/README.md)
  - Output: create `src/benchwarmer/adapters/hermes/{__init__,capabilities,reader}.py`,
    `tests/fixtures/hermes/schema-30/`, and
    `tests/adapters/hermes/test_reader.py`
  - Acceptance: open a configured profile database read-only, record application
    and schema versions separately, validate the schema-30 capability manifest,
    read a consistent WAL-aware snapshot, and fail closed on unsupported schemas
    or missing identity columns; commit only synthetic fixtures
  - Verify: focused reader tests plus all Python checks

- [ ] Import Hermes conversations incrementally
  - Dependencies: [Read supported Hermes histories without modifying them](../hermes-import/README.md), [Add shared conversation records and synthetic source examples](../conversation-contracts/README.md) (already recorded)
  - Output: create `src/benchwarmer/adapters/hermes/importer.py`, importer tests,
    and migrations for Hermes session, message, usage, snapshot-provenance,
    coverage, and cursor state
  - Acceptance: source-native upserts and post-commit watermark advancement make
    initial, unchanged, appended, mutable-usage, and interrupted imports
    idempotent without erasing prior evidence; map messages and continuation links
    to the shared conversation contract without losing native snapshots
  - Verify: focused importer fixtures, migration round trip, and all Python checks

- [ ] Reconcile Hermes changes and validate private imports
  - Dependencies: [Import Hermes conversations incrementally](../hermes-import/README.md)
  - Output: create `src/benchwarmer/adapters/hermes/reconcile.py`, reconciliation
    tests, and `docs/verification/hermes-import.md` with sanitized results only
  - Acceptance: detect edits, disappearance, metadata and usage changes,
    source-side deletion, missing watermarks, schema changes, and source
    replacement without deleting retained private snapshots or exposing private
    identifiers and content
  - Verify: focused reconciliation scenarios, sanitized private-source checks,
    and all Python checks

## Verification

Before implementing a broad step, specify its files, fixtures, and focused
checks here. Follow [repository validation](../../../AGENTS.md) and record actual
results at handoff. This record currently defines planned work.

## Supporting material

- [Current priorities](../../TODO.md)
- [Conversation workflow](../../../docs/conversation-library.md)
- [Experiment semantics](../../../docs/experiments.md)
- [First-adapter decision](../../../docs/decisions/0004-first-import-adapter.md)
- [Hermes source evidence](../../../docs/sources/hermes.md), refresh before implementation
