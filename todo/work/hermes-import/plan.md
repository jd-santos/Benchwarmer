# Hermes import implementation plan

## Problem

Hermes is the first real conversation source, but its live database is on a
separate device from the central Benchwarmer installation. Benchwarmer needs to
read that database without modifying it, preserve source-native evidence, import
records idempotently, and eventually deliver them through the accepted manual
push collector topology.

The first implementation milestone is the read-only Hermes adapter. It must be
useful and testable before the collector protocol exists, without introducing a
temporary archive-transfer format that could become a second ingestion path.

## Decisions

- Build the Hermes adapter first, then connect it to the permanent manual push
  collector from ADR 0005. Do not add a temporary manually copied bundle format.
- Treat the Hermes application version and database schema version as separate
  evidence. The first manifest targets database schema 30 because that is the
  layout previously observed in the active profile and a newer source checkout.
- Fail closed on unsupported schema versions, missing identity columns,
  incompatible primary keys, or changed required capabilities. Additive unknown
  columns are evidence to preserve, not semantics to infer.
- Keep normalized conversation schema version 1 stable during the Hermes slice.
  Source-specific fields stay in versioned Hermes extensions until the separate
  source-verification task establishes a justified shared-schema change.
- Use only synthetic fixtures in Git. Private rows, paths, profile names, account
  identifiers, snapshots, logs, and verification output stay under private data
  roots outside the checkout.
- Keep import separate from execution. Reading Hermes must never resume a
  session, call a provider, load execution credentials, or run captured tools.
- Treat source deletion and disappearance as observations. They never authorize
  deletion of retained Benchwarmer evidence.

## Milestone 1: read schema-30 histories without modifying Hermes

**Type:** subsystem or file cluster `[context: medium]`

### Files

Create:

- `src/benchwarmer/adapters/__init__.py`
- `src/benchwarmer/adapters/hermes/__init__.py`
- `src/benchwarmer/adapters/hermes/capabilities.py`
- `src/benchwarmer/adapters/hermes/reader.py`
- `tests/adapters/hermes/test_reader.py`
- `tests/fixtures/hermes/schema-30/schema.sql`
- `tests/fixtures/hermes/schema-30/expected.json`
- `tests/fixtures/hermes/schema-30/README.md`

Do not add a new dependency or a global Hermes environment variable. The later
collector configuration owns the private database path and application version.
The reader receives them as explicit inputs.

### Capability contract

`capabilities.py` owns an immutable, adapter-versioned schema-30 manifest. It
classifies tables, columns, primary keys, and source semantics as required or
optional for this adapter version.

The first manifest covers the source records needed by the accepted adapter
decision:

- session identity, continuation, timestamps, mutable metadata, prompt linkage,
  archive/pin state, aggregate usage, and source metadata;
- message identity, session relationship, ordering time, role, content,
  reasoning, tool calls/results, finish state, optional platform identity, and
  mutable flags;
- the complete `session_model_usage` identity and token/cost provenance fields;
- system-prompt lookup needed by referenced sessions; and
- schema/application evidence and unknown-column coverage.

Gateway routing is not part of the first normalized import. If present, report
its coverage and preserve it only in the private raw snapshot. Its presence must
not silently expand the reader contract.

The manifest must distinguish:

- required identity and relationship columns, whose absence is fatal;
- required payload columns whose absence makes schema 30 incompatible;
- optional version-gated columns, whose absence becomes explicit coverage; and
- additive unknown columns, which remain raw private evidence.

Capability errors identify only bounded table, column, index, or schema names.
They must not contain row values, source paths, profile names, or SQL payloads.

### Reader contract

`reader.py` provides immutable input and result records plus one public read
operation. Exact names may follow existing project conventions, but the public
seam must expose:

- an absolute configured SQLite path supplied by the caller;
- the caller-observed Hermes application version when available;
- the independently observed database schema version;
- the adapter and capability-manifest versions;
- journal mode and capability/coverage evidence;
- source rows grouped by table with source column names retained; and
- a stable source ordering suitable for the later importer.

The reader must:

1. Reject relative, missing, non-file, or unusable source paths without echoing
   private paths in errors.
2. Open SQLite through a URI in read-only mode, enable query-only behavior, and
   never initialize, migrate, checkpoint, vacuum, attach, or write the source.
3. Start one explicit read transaction before capability inspection and row
   reads so every returned table reflects one consistent SQLite snapshot.
4. Observe committed WAL content. Copying `state.db` without its WAL is not a
   supported read strategy.
5. Validate the schema capability manifest before reading private payload rows.
6. Read deterministic table and row order using source-native identities rather
   than timestamps, titles, or paths as keys.
7. Preserve SQLite scalar values and unknown source columns in the private raw
   representation without trying to assign unverified meanings.
8. Return explicit coverage for unavailable, optional, and unknown fields.
9. Close the transaction and connection on success or failure.
10. Keep exceptions and ordinary output bounded and free of private content.

The reader does not write Benchwarmer snapshots or normalized records. That
transaction boundary belongs to the incremental importer milestone.

### Synthetic fixtures and tests

The schema-30 fixture contains only invented values and documents its synthetic
origin. Tests create disposable SQLite databases from the SQL fixture rather
than committing a database copied from Hermes.

Focused tests cover:

- valid schema-30 capability negotiation;
- application version and schema version remaining distinct;
- committed rows still resident in WAL being visible to the reader;
- one consistent snapshot across related table reads;
- deterministic ordering and preservation of explicit nulls and unknown columns;
- optional-column coverage;
- unsupported schema versions;
- missing tables, identity columns, foreign relationships, or primary-key parts;
- additive columns that remain raw and do not gain normalized meaning;
- a query-only source connection and unchanged source database content;
- cleanup after success and failure; and
- bounded exceptions that do not echo synthetic sentinel values or source paths.

### Source-device verification

The source device can run the repository’s Python tooling, and the operator can
provide an approved read-only host mount for the Hermes database. That setup is
not immediately available and is not a reason to weaken fixture coverage.

When the device is available:

1. Refresh only schema evidence first: Hermes application version, database
   schema version, journal mode, table names, column names, primary keys, indexes,
   and foreign keys. Do not inspect row counts or values during this step.
2. Compare the observation with the checked-in capability manifest. If it
   differs, stop and revise fixtures deliberately rather than accepting it as
   schema 30 by name alone.
3. Run the focused reader checks against the approved read-only mount.
4. Only after capability validation, perform a private-row read into an
   owner-only Benchwarmer data root outside the checkout.
5. Record only sanitized pass/fail, versions, capability coverage, and bounded
   counts in `docs/verification/hermes-import.md`. Never record paths, profile
   names, IDs, content, prompts, or account metadata.

Private validation is required before this milestone is called complete, but its
later scheduling does not block implementation and synthetic validation.

### Validation

Run from the repository root:

```bash
uv run pytest tests/adapters/hermes/test_reader.py
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run python -m compileall src
git diff --check
```

Also run active diagnostics on every changed Python file. The source-device gate
adds the sanitized private verification described above.

## Milestone 2: import Hermes incrementally

Split this milestone so schema work and import behavior remain reviewable.

### 2A. Persistence and migrations

**Type:** subsystem or file cluster `[context: medium]`

Add migrations and source-neutral records for native session/message/usage
subjects, immutable snapshot references, source-presence observations, and the
Hermes cursor. Do not encode Hermes-only columns into source-neutral tables when
versioned extensions or native snapshot references preserve them accurately.

Migration tests must cover upgrade/downgrade, constraints, source-scoped native
identity, and retention of prior observations.

### 2B. Import transaction

**Type:** subsystem or file cluster `[context: medium]`

Build `src/benchwarmer/adapters/hermes/importer.py` around the reader and existing
`Source` and `ImportBatch` contracts. The import unit must publish immutable
private snapshot content before committing its references, upsert source-native
subjects idempotently, and advance the message watermark only after the entire
unit commits.

Test initial, unchanged, appended, metadata-only, mutable-usage, interrupted, and
retry cases. A zero actual-cost value remains unconfirmed unless its source
status and provenance establish a charge.

## Milestone 3: deliver through the permanent collector

**Type:** future subsystem cluster `[context: large]`

After the source adapter and importer core pass synthetic and source-device
checks, implement the manual push path from ADR 0005 under the cross-machine
collection work record. Decompose it before implementation into bounded protocol,
enrollment, spool, central ingestion, and acknowledgment packets.

Hermes is the first adapter carried by that protocol. The central library does
not claim real Hermes availability until an enrolled source device has delivered
a bounded batch and received acknowledgment only after durable snapshot and
normalized-record commit.

This milestone must not introduce a temporary manual-copy protocol, source-side
listener, Docker socket access, remote shell requirement, background scheduler,
or model work. Optional scheduling follows only after manual collection is
reliable.

## Milestone 4: reconcile and validate retained evidence

**Type:** subsystem or file cluster `[context: medium]`

Build `src/benchwarmer/adapters/hermes/reconcile.py` after incremental imports and
manual delivery are stable. Reconciliation detects edits, disappeared keys,
source deletion, metadata and usage changes, missing or invalid watermarks,
schema changes, and source-replacement conflicts without deleting retained
snapshots.

Choose the full-reconciliation trigger from measured source size and run time.
Do not invent a time interval before that evidence exists. Always allow an
explicit operator-triggered reconciliation and require one after adapter or
schema upgrades.

## Deferred source research

The P2 work record at
[`../additional-source-research/README.md`](../additional-source-research/README.md)
owns refreshed Codex, Claude Desktop/Code, and OpenRouter research. Earlier
subagent attempts did not complete full-page source verification because their
search/fetch providers were unavailable, so their provisional output is not an
accepted project source.

That task may propose a versioned shared conversation schema change after
successful official-source research and separately approved authenticated
read-only probes. It does not block the Hermes schema-30 reader, and it must not
retroactively reinterpret Hermes source fields without migration and provenance.

## Rejected alternatives

### Temporary manually copied archives

Rejected because they create a second ingestion path with weaker acknowledgment,
idempotency, and retry semantics than ADR 0005. A one-off transfer mechanism can
easily become permanent operational behavior.

### Full collector before proving the reader

Rejected because it puts enrollment, credentials, networking, spooling, and
central ingestion on the critical path before source capability negotiation is
known to work.

### Supporting every observed Hermes schema immediately

Rejected because an application version does not prove a database layout. Each
supported schema requires its own sanitized fixture, manifest, and compatibility
evidence.

### Revising normalized conversation v1 from provisional research

Rejected because the available alternate-source research was not fully fetched
and verified. Hermes-specific evidence fits the existing extension and coverage
contracts while that research remains pending.
