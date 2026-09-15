# TODO

Use [roadmap.md](roadmap.md) for milestone order and dependency gates. The
foundation build plan is
[plans/2026-09-07-application-foundation.md](plans/2026-09-07-application-foundation.md).
The first conversation-library slice follows
[plans/2026-09-15-conversation-contracts.md](plans/2026-09-15-conversation-contracts.md).
Architecture rationale belongs in the design docs, not in this queue.

A handoff-ready item has a unique ID, dependencies, exact output or files,
acceptance criteria, and verification commands.

## Claim protocol

Only a coordinating agent may move an item between sections. Research,
decision, and implementation subagents claim work through that coordinator so
one task does not modify this queue while another edits the same file.

When the coordinator assigns work, add exactly one metadata line beneath the
task:

```markdown
  - Claim: owner `agent:<name-or-session>`, branch `task/<id>-<slug>`, started
    `YYYY-MM-DDTHH:mm:ssZ`
```

## In Progress

- [ ] **LIB-001: Add shared conversation records and synthetic source examples**
  - Claim: owner `agent:library-contract`, branch `task/conversation-library`,
    started `2026-09-15T01:14:12Z`
  - Status: implementation integrated and final review clean. All 14 focused
    supplemental tests pass on Python 3.14.7. Canonical pytest, Ruff, format, and
    compile checks each exit 2 because the pinned runtime is absent; retain In
    Progress until that validation blocker is resolved.
  - [x] Handoff prepared at ~51% context
  - Resume: [conversation handoff](plans/2026-09-15-conversation-handoff.md);
    delegation smoke test passed after reload
  - Execution: isolated managed-worktree patch integrated into the claim branch
  - Type: Subsystem or file cluster `[context: medium]`
  - Dependencies: `PLAN-003`, `FND-002`
  - Plan: LIB-001 in the conversation-contracts plan
  - Output: `src/benchwarmer/conversations.py`, `tests/test_conversations.py`,
    `tests/fixtures/conversations/`
  - Acceptance: versioned strict JSON round trips, source provenance, branches,
    tool/artifact linkage and explicit gaps; synthetic inputs only
  - Verify: plan's focused tests, Python checks, and documented runtime blockers

- [ ] **ENR-001: Add bounded model-work plans and exact approval validation**
  - Claim: owner `agent:model-work-contract`, branch `task/conversation-library`,
    started `2026-09-15T01:14:12Z`
  - Status: implementation integrated and final review clean. All 14 focused
    supplemental tests pass on Python 3.14.7. Canonical pytest, Ruff, format, and
    compile checks each exit 2 because the pinned runtime is absent; retain In
    Progress until that validation blocker is resolved.
  - [x] Handoff prepared at ~51% context
  - Resume: [conversation handoff](plans/2026-09-15-conversation-handoff.md);
    delegation smoke test passed after reload
  - Execution: isolated managed-worktree patch integrated into the claim branch
  - Type: Focused change `[context: medium]`
  - Dependencies: `PLAN-003`, `FND-002`
  - Plan: ENR-001 in the conversation-contracts plan
  - Output: `src/benchwarmer/model_work.py`, `tests/test_model_work.py`
  - Acceptance: immutable input/stage/limit plans; stale or missing approval fails;
    no provider calls, scheduler, or durable-budget guarantee
  - Verify: plan's focused tests, Python checks, and documented runtime blockers

## Up Next

Prioritize the conversation library over usage reporting. `COL-001` accepted the
manual-first push topology in ADR 0005. `COL-002` remains blocked on the first
importer and foundation gates. The remaining foundation supports real
persistence/API delivery, and `DEP-003` stays blocked through `QA-004`.

The WAL-safe provisioner is implemented, but its pinned runtime was absent from
this checkout at the contract-slice baseline. Canonical `uv run` checks could not
start. The user authorized rebuilding it to validate `LIB-001` and `ENR-001`.

- [ ] **FND-003 — Implement private data-root configuration**
  - Dependencies: `FND-002`, `DEC-001`, `ENV-001`
  - Plan: Task 3 in the foundation plan
  - Verify: focused config tests, ADR 0002's disposable recovery prototype, and
    all `FND-002` checks

- [ ] **FND-004 — Add database migration plumbing**
  - Dependencies: `FND-003`
  - Plan: Task 4 in the foundation plan
  - Verify: temporary-database Alembic current/upgrade/downgrade commands and
    focused tests

- [ ] **FND-005 — Add truthful unmigrated API health**
  - Dependencies: `FND-004`
  - Plan: Task 5 in the foundation plan
  - Verify: API tests, all Python checks, and a real loopback HTTP request

- [ ] **FND-006 — Add source records and migration**
  - Dependencies: `FND-004`
  - Plan: Task 6 in the foundation plan
  - Verify: migration round-trip and focused model tests

- [ ] **FND-007 — Add import-batch records and migration**
  - Dependencies: `FND-006`
  - Plan: Task 7 in the foundation plan
  - Verify: migration round-trip and focused model tests

- [ ] **FND-008 — Verify the real database revision in health**
  - Dependencies: `FND-005`, `FND-007`
  - Plan: Task 8 in the foundation plan
  - Verify: health tests for unmigrated and migrated temporary databases

- [ ] **FND-009 — Add sanitized source fixture loading**
  - Dependencies: `FND-007`
  - Plan: Task 9 in the foundation plan
  - Verify: deterministic, idempotent fixture-load command and focused tests

- [ ] **FND-010 — Expose fixture-backed source status**
  - Dependencies: `FND-008`, `FND-009`
  - Plan: Task 10 in the foundation plan
  - Verify: service/API contract tests plus all Python checks

- [ ] **UI-003 — Add the first useful home page**
  - Dependencies: `UI-002`, `UI-004`
  - Plan: Task 14 in the foundation plan
  - Verify: loading/healthy/unmigrated/error UI tests and frontend checks

- [ ] **UI-005 — Connect the source status page**
  - Dependencies: `FND-010`, `UI-003`, `UI-004`
  - Plan: Task 15 in the foundation plan
  - Verify: populated/empty/error UI tests, frontend checks, and Svelte MCP
    autofixer review where available

- [ ] **QA-001 — Add the disposable browser process harness**
  - Dependencies: `FND-010`, `UI-005`
  - Plan: Task 16 in the foundation plan
  - Verify: Playwright starts, migrates, seeds, stops, and cleans up disposable
    processes/state

- [ ] **QA-002 — Verify desktop and mobile browser flows**
  - Dependencies: `QA-001`
  - Plan: Task 17 in the foundation plan
  - Verify: `npm --prefix web run test:e2e` at desktop and 375px viewports

- [ ] **QA-003 — Verify API restart persistence**
  - Dependencies: `QA-002`
  - Plan: Task 18 in the foundation plan
  - Verify: migrated fixture records survive an API process restart; the
    stateless frontend does not own persistence

- [ ] **QA-004 — Document development and final integration**
  - Dependencies: `QA-003`
  - Plan: Task 19 in the foundation plan; run its Final integration gate
  - Output: `docs/development.md`
  - Acceptance: a fresh checkout can migrate disposable state, start both
    processes, and pass desktop/mobile/restart flows with no private or
    generated artifacts tracked

- [ ] **DEP-003 — Implement and validate private deployment**
  - Dependencies: `DEC-001`, `QA-004`
  - Output: implement the application container and declarative Tailscale Serve
    route, then record a sanitized deployment verification in the same PR
  - Verify: render Compose, confirm no published app port, test
    authorized/unauthorized reachability, compare Alembic head, and exercise
    crash restart, operator stop, and unhealthy alert
  - Acceptance: all checks in ADR 0003 pass on the Mac mini before deployment is
    called operational

## Backlog

Items remain milestone-sized until their prerequisites make exact
decomposition possible. Decompose one into handoff-ready IDs before
implementation.

- [ ] **ACT-001 — Implement the first idempotent incremental importer**
  - Dependencies: `ACT-HERMES-003`
  - Decomposition: `ACT-HERMES-001` through `ACT-HERMES-003`; close this
    milestone item only after all three pass
- [ ] **ACT-HERMES-001 — Add the schema-gated read-only Hermes source reader**
  - Dependencies: `SRC-002`, `FND-010`, `QA-004`
  - Output: create `src/benchwarmer/adapters/hermes/{__init__,capabilities,reader}.py`,
    `tests/fixtures/hermes/schema-30/`, and
    `tests/adapters/hermes/test_reader.py`
  - Acceptance: open a configured profile database read-only, record application
    and schema versions separately, validate the schema-30 capability manifest,
    read a consistent WAL-aware snapshot, and fail closed on unsupported schemas
    or missing identity columns; commit only synthetic fixtures
  - Verify: focused reader tests plus all Python checks
- [ ] **ACT-HERMES-002 — Implement transactional incremental Hermes imports**
  - Dependencies: `ACT-HERMES-001`, `LIB-001`
  - Output: create `src/benchwarmer/adapters/hermes/importer.py`, importer tests,
    and migrations for Hermes session, message, usage, snapshot-provenance,
    coverage, and cursor state
  - Acceptance: source-native upserts and post-commit watermark advancement make
    initial, unchanged, appended, mutable-usage, and interrupted imports
    idempotent without erasing prior evidence; map messages and continuation links
    to the shared conversation contract without losing native snapshots
  - Verify: focused importer fixtures, migration round trip, and all Python checks
- [ ] **ACT-HERMES-003 — Add Hermes reconciliation and private-source validation**
  - Dependencies: `ACT-HERMES-002`
  - Output: create `src/benchwarmer/adapters/hermes/reconcile.py`, reconciliation
    tests, and `docs/verification/hermes-import.md` with sanitized results only
  - Acceptance: detect edits, disappearance, metadata and usage changes,
    source-side deletion, missing watermarks, schema changes, and source
    replacement without deleting retained private snapshots or exposing private
    identifiers and content
  - Verify: focused reconciliation scenarios, sanitized private-source checks,
    and all Python checks
- [ ] **ACT-002: Deliver conversation browsing and text/metadata search**
  - Type: Subsystem or file cluster `[context: large]`; decompose before launch
  - Dependencies: `ACT-001`
  - Scope: readable transcripts, branches/continuations, source freshness,
    coverage, filters and evidence-linked keyword search; usage/cost as metadata,
    no chart dependency
- [ ] **COL-002: Implement approved cross-machine collection**
  - Type: Subsystem or file cluster `[context: large]`; decompose before launch
  - Dependencies: `COL-001`, `LIB-001`, `ACT-001`, `QA-004`
  - Scope: manual push collector first, versioned enrollment and upload protocol,
    source allowlists, bounded private spool/backfill, durable acknowledgment,
    duplicate delivery and revocation tests; add optional `launchd` scheduling
    only after the manual path is reliable
  - Gate: exact files, limits, transport, packaging, and tests must follow
    [ADR 0005](decisions/0005-cross-machine-collection.md); operational rollout
    also requires `DEP-003`
- [ ] **ENR-002: Implement durable approved model-work execution**
  - Type: Subsystem or file cluster `[context: large]`; decompose before launch
  - Dependencies: `ENR-001`, `ACT-002`
  - Scope: preview/approval UI, disclosure checks, durable request/cost reservations,
    cancellation, bounded retries and outcome-unknown recovery
  - Gate: no model stage dispatch before its durable safety tests pass
- [ ] **ENR-003: Add approved description and classification enrichment**
  - Type: Subsystem or file cluster `[context: medium]`
  - Dependencies: `ENR-002`
  - Scope: choose first fields and small/large model tiers using approved samples;
    preserve source short summaries, generated revisions, evidence, usage/cost
- [ ] **ENR-004: Expand task-aware enrichment fields and segmentation**
  - Type: Subsystem or file cluster `[context: large]`; decompose before launch
  - Dependencies: `ENR-003`
  - Scope: topics, task types, projects, technologies, entities, outcomes,
    interventions/retries, quality signals, segmentation and suggested criteria;
    measured model-tier routing, no unapproved automatic escalation
- [ ] **SEARCH-001: Add semantic discovery alongside text/filter search**
  - Type: Subsystem or file cluster `[context: medium]`
  - Dependencies: `ENR-002`, `ACT-002`
  - Scope: approved embeddings/query actions; message, description, tool and
    extracted artifact search; visible index coverage and source-passage links
- [ ] **DATA-001: Add projects, live collections and frozen datasets**
  - Type: Subsystem or file cluster `[context: medium]`
  - Dependencies: `ACT-002`, `LIB-001`
  - Scope: saved queries and exact pinned membership/source/enrichment revisions;
    collection growth never triggers model work
- [ ] **DATA-002: Provide versioned private query and dataset export access**
  - Type: Focused change `[context: medium]`
  - Dependencies: `DATA-001`
  - Scope: local read/query API and private export for scripts/notebooks; no
    dependency on UI automation or unstable internal database tables
- [ ] **REV-001 — Add ratings, labels, notes, and annotation revision history**
  - Dependencies: `ACT-002`
- [ ] **ACT-003 — Add a second source adapter**
  - Dependencies: `ACT-001`
  - Promotion requirement: the coordinator names the exact second-source task
    ID and inspection report dependency before implementation
- [ ] **ACT-004: Add the remaining Pi/Codex/Hermes source adapter**
  - Type: Subsystem or file cluster `[context: medium]`
  - Dependencies: `ACT-003`
  - Gate: refresh source evidence and name exact adapter tasks before launch
- [ ] **REC-001 — Reconcile overlapping harness/provider observations**
  - Dependencies: `ACT-003`
- [ ] **REC-002 — Expose gaps and reconciliation decisions in API and UI**
  - Dependencies: `REC-001`
- [ ] **RPT-001: Add detailed usage and economics reporting**
  - Type: Subsystem or file cluster `[context: medium]`
  - Dependencies: `ACT-002`, `REC-002`
  - Priority: follows useful conversation discovery; never a library gate
- [ ] **EVD-001 — Add trusted external evidence with immutable revisions**
  - Dependencies: `ACT-002`, `REV-001`
  - Priority: deferred behind conversation discovery and reusable datasets
- [ ] **MOD-001 — Add model/configuration evidence views**
  - Dependencies: `ACT-002`, `EVD-001`
- [ ] **TSK-001: Prepare meaningful task units from frozen datasets**
  - Dependencies: `DATA-001`
  - Scope: one-to-few-exchange units, sufficient context, segmentation provenance,
    correlated source lineage, reconstruction gaps and leakage checks
  - Promotion requirement: the coordinator names the first task-family and
    reconstruction decision IDs before implementation
- [ ] **EXP-001 — Build the experiment safety substrate**
  - Dependencies: `TSK-001`, `ENR-002`
  - Scope: disposable workspaces, fixed scripts, capability checks, credential
    and network policy, budgets, cancellation, durable progress, attempt
    reservation, outcome-unknown reconciliation, and duplicate-paid-work
    protection
  - Promotion requirement: no real or paid trial may be dispatched before this
    task is complete
- [ ] **JDG-001: Add applied-judge configuration and automatic bounded judging**
  - Type: Subsystem or file cluster `[context: medium]`
  - Dependencies: `TSK-001`, `ENR-002`
  - Scope: frozen rubrics, judge model/configuration, deterministic checks where
    useful, evidence, disagreement, calibration and unjudged states
- [ ] **EXP-002 — Run native harness and compatible direct-API trials**
  - Dependencies: `EXP-001`, `JDG-001`
  - Scope: automatic applied judges inside the same approved rerun budget
  - Promotion requirement: the coordinator names harness, permission, and
    budget decision IDs before implementation
- [ ] **EXP-003 — Compare criterion-level quality and economics per trial**
  - Dependencies: `EXP-002`
- [ ] **EXP-004 — Add controlled comparisons with explicit overrides**
  - Dependencies: `EXP-003`
  - Promotion requirement: the coordinator adds a controlled-comparison
    decision task ID before implementation
- [ ] **SIM-001: Add later adaptive user continuation**
  - Type: Subsystem or file cluster `[context: large]`; decompose before launch
  - Dependencies: `EXP-003`, user-approved simulator policy
  - Scope: intent-preserving follow-ups, separate simulator provenance/cost,
    allowed-knowledge and leakage checks; never label as exact replay
- [ ] **SUITE-001 — Promote useful tasks into repeatable evaluation suites**
  - Dependencies: `EXP-003`
- [ ] **EXPORT-001 — Add deliberately sanitized exports and portable reports**
  - Dependencies: `EXP-003`
  - Promotion requirement: the coordinator adds stable-schema and privacy
    review task IDs before implementation

## Done

- [x] **COL-001: Plan collection from the user's other machines**
  - Accepted [ADR 0005](decisions/0005-cross-machine-collection.md): one
    manual-first push collector per Mac, durable private spooling and central
    acknowledgment, optional scheduled runs, and no desktop/cloud sync

- [x] **PLAN-003: Prioritize the conversation library and bounded evaluations**
  - Captured cross-machine collection planning, shared evidence, enrichment,
    search, datasets, automatic applied judges and later adaptive continuation
  - Added the two-lane executable conversation-contract slice; no live collection
    topology, remote disclosure permission, or numeric spend budget assumed

- [x] **PLAN-001 — Define the local app direction and evaluation semantics**
  - Tailscale access, mobile UI, private snapshots, usage aggregation, harness
    dimensions, native configurations, and system-prompt provenance documented
- [x] **PLAN-002 — Create the buildout roadmap and first agent handoff plan**
  - Milestone dependencies, acceptance gates, task IDs, exact foundation
    paths, and verification commands documented

- [x] **SRC-PI-001 — Inspect Pi capabilities**
  - Added and independently reviewed [Pi evidence](sources/pi.md)
- [x] **SRC-HERMES-001 — Inspect Hermes capabilities**
  - Added and independently reviewed [Hermes evidence](sources/hermes.md)
- [x] **SRC-CODEX-001 — Inspect Codex capabilities**
  - Added and independently reviewed [Codex evidence](sources/codex.md)
- [x] **SRC-OPENROUTER-001 — Inspect OpenRouter capabilities**
  - Added and independently reviewed [OpenRouter evidence](sources/openrouter.md)
- [x] **SRC-001 — Synthesize the source coverage matrix**
  - Compared source identity, imports, usage, economics, classification, prompt,
    execution, retention, and reconciliation without choosing an adapter
- [x] **FND-001 — Record application foundation defaults**
  - Accepted [ADR 0001](decisions/0001-application-foundation.md)
- [x] **DEP-001 — Decide the private data and recovery boundary**
  - Accepted [ADR 0002](decisions/0002-data-recovery.md) with WAL and restored-path
    safety gates
- [x] **DEP-002 — Decide private serving and supervision**
  - Accepted [ADR 0003](decisions/0003-serving-supervision.md); live deployment
    remains gated by `DEP-003`
- [x] **DEC-001 — Integrate the initial decision records**
  - Reconciled all three ADRs, the foundation plan, `ENV-001`, and `DEP-003`
- [x] **SRC-002 — Select the first import adapter**
  - Accepted [ADR 0004](decisions/0004-first-import-adapter.md), selecting a
    schema-gated read-only Hermes adapter with explicit reconciliation
- [x] **FND-002 — Add Python test and lint tooling**
  - Added pytest, Ruff, a package smoke test, locked development dependencies,
    and executable repository commands
- [x] **UI-001 — Scaffold SvelteKit with the selected adapter and checks**
  - Added the pinned SvelteKit TypeScript scaffold, static `200.html` fallback,
    client-side rendering configuration, lint, formatting, and unit checks
- [x] **ENV-001 — Provision a WAL-safe SQLite runtime**
  - Added the immutable source-built Python 3.13.15 and SQLite 3.53.4 runtime,
    pre-connection WAL gate, fail-closed provisioning, and recovery guidance
- [x] **UI-002 — Build the responsive application shell**
  - Added task-focused navigation, responsive layout, keyboard and touch
    behavior, visible focus, reduced motion, and component tests
- [x] **UI-004 — Add the typed API client and `/api` proxy**
  - Added validated health/source contracts, same-origin requests, typed failure
    states, cancellation, and the server-configured development proxy
