# Import Hermes conversations reliably

Status: In progress on `task/hermes-import`. The schema-30 reader is the first implementation milestone. Source-device verification is approved but pending operator availability.

## Purpose

Make the first real histories available for browsing while retaining private native evidence and explicit capture gaps.

## Dependencies and order

The [application foundation](../application-foundation/README.md), shared conversation contract, and first-adapter decision are complete or accepted. Follow the [implementation plan](plan.md): prove the adapter and importer core first, then carry Hermes through the permanent manual push collector from ADR 0005. Do not create a temporary archive-transfer path.

The live Hermes database is on a separate device. That device can run the repository tooling, and the operator can expose an approved read-only host mount when available. Real central-library availability therefore finishes across this record and [cross-machine collection](../cross-machine-collection/README.md).

## Acceptance criteria

Initial, unchanged, appended, interrupted, edited, and source-deleted histories import without duplicating or erasing retained evidence. Source versions and unsupported schemas remain visible; public fixtures are synthetic. The source device never exposes a listener or writable Hermes database, and the central library does not claim real Hermes availability before durable collector acknowledgment.

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
  - Plan: [Reader milestone](plan.md#milestone-1-read-schema-30-histories-without-modifying-hermes)
  - Verify: focused reader tests plus all Python checks
  - [ ] Define the schema-30 capability manifest and synthetic fixture
  - [ ] Implement and test the WAL-aware read-only snapshot reader
  - [ ] Refresh schema-only evidence and run sanitized private validation on the source device

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

The implementation plan defines the files, privacy boundary, focused tests, repository checks, and deferred source-device gate for the active reader milestone. Follow [repository validation](../../../AGENTS.md) and record actual results at handoff. Do not mark the reader complete until both synthetic validation and sanitized private source-device validation pass.

## Supporting material

- [Current priorities](../../TODO.md)
- [Conversation workflow](../../../docs/conversation-library.md)
- [Experiment semantics](../../../docs/experiments.md)
- [Implementation plan](plan.md)
- [First-adapter decision](../../../docs/decisions/0004-first-import-adapter.md)
- [Hermes source evidence](../../../docs/sources/hermes.md), refresh before private validation
- [Additional-source research](../additional-source-research/README.md)
