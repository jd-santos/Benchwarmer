# Import Hermes conversations reliably

Status: Reader and incremental importer are implemented on `task/hermes-import`; source-device verification, manual collection, and reconciliation remain pending. The importer requires an idle SQLAlchemy session and records only synthetic validation results in Git.

## Purpose

Make the first real histories available for browsing while retaining private native evidence and explicit capture gaps.

## Dependencies and order

The [application foundation](../application-foundation/README.md), shared conversation contract, and first-adapter decision are complete or accepted. Follow the [implementation plan](./plan.md): prove the adapter and importer core first, then carry Hermes through the permanent manual push collector from ADR 0005. Do not create a temporary archive-transfer path.

The live Hermes database is on a separate device. That device can run the repository tooling, and the operator can expose an approved read-only host mount when available. Real central-library availability therefore finishes across this record and [cross-machine collection](../cross-machine-collection/README.md).

## Acceptance criteria

The reader and incremental importer cover initial, unchanged, appended, mutable-usage, edited-message, interrupted, and retry cases without duplicating or erasing retained evidence. Source versions and unsupported schemas remain visible; public fixtures are synthetic. Full source deletion detection and retained-presence reconciliation are a separate milestone. The source device never exposes a listener or writable Hermes database, and the central library does not claim real Hermes availability before durable collector acknowledgment.

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
  - Plan: [Reader milestone](./plan.md#milestone-1-read-schema-30-histories-without-modifying-hermes)
  - Verify: focused reader tests plus all Python checks
  - [x] Define the schema-30 capability manifest and synthetic fixture
  - [x] Implement and test the WAL-aware read-only snapshot reader
  - [ ] Refresh schema-only evidence and run sanitized private validation on the source device

- [x] Import Hermes conversations incrementally
  - Dependencies: [Read supported Hermes histories without modifying them](../hermes-import/README.md), [Add shared conversation records and synthetic source examples](../conversation-contracts/README.md) (already recorded)
  - Output: create `src/benchwarmer/adapters/hermes/importer.py`, importer tests,
    and migrations for Hermes session, message, usage, snapshot-provenance,
    coverage, and cursor state
  - Acceptance: source-native upserts and post-commit watermark advancement make
    initial, unchanged, appended, mutable-usage, and interrupted imports
    idempotent without erasing prior evidence; map messages and continuation links
    to the shared conversation contract without losing native snapshots
  - Verify: focused importer fixtures, migration round trip, active diagnostics, and all Python checks
  - [x] Add source-native migrations, private content-addressed snapshots, cursor state, presence records, and normalized revisions
  - [x] Implement atomic upsert/publish behavior with bounded failed-batch records and idempotent retries
  - [x] Test initial, unchanged, appended, edited/tool-linked, mutable-usage, interrupted, and source-read-failure paths

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

The reader uses the public schema-30 definitions pinned to
NousResearch/hermes-agent commit
`693641aa8b4359c602283bdbbc14041e03bc47bc`. It reads the source schema
version from Hermes's `schema_version` table, keeps the capability-manifest
version independent, requires the repository's WAL-safe SQLite runtime, opens
the configured database read-only, verifies `query_only` and WAL mode, and
validates required keys and relationships before reading private rows.

Actual checks on `task/hermes-import`:

- `uv run pytest tests/adapters/hermes/test_reader.py tests/adapters/hermes/test_importer.py -q`: reader and importer checks pass
- `uv run pytest`: 204 passed with one upstream Starlette/AnyIO deprecation
  warning
- `uv run ruff check .`: passed
- `uv run ruff format --check .`: 101 files already formatted
- `uv run python -m compileall src`: passed
- `git diff --check`: passed
- Active diagnostics on changed Python paths: no findings

Independent review found and corrected the initial fixture's wrong
schema-version mechanism, invented column names, missing WAL runtime gate,
manifest-version conflation, incomplete relationship checks, and
exception-context disclosure. Follow-up review confirmed the corrected pinned
schema and read transaction. SQLite SHM lock/index bytes are intentionally
excluded from byte-equality assertions because readers legitimately update
transient shared-memory coordination. Persisted database and WAL bytes remain
unchanged.

Do not mark the reader parent item complete until the sanitized source-device
validation passes. The incremental persistence milestone is complete for synthetic
fixtures. Central collector delivery and full reconciliation remain pending milestones.

## Supporting material

- [Current priorities](../../TODO.md)
- [Conversation workflow](../../../docs/conversation-library.md)
- [Experiment semantics](../../../docs/experiments.md)
- [Implementation plan](./plan.md)
- [First-adapter decision](../../../docs/decisions/0004-first-import-adapter.md)
- [Hermes source evidence](../../../docs/sources/hermes.md), refresh before
  private validation
- [Additional-source research](../additional-source-research/README.md)
