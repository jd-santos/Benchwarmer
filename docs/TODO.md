# TODO

Use [roadmap.md](roadmap.md) for milestone order and dependency gates. The
first executable build plan is
[plans/2026-09-07-application-foundation.md](plans/2026-09-07-application-foundation.md).
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

## Up Next

The four source inspections can run in parallel because each writes a distinct
`docs/sources/<name>.md` file. Foundation decision proposals may also run in
parallel because each writes one assigned ADR. A coordinator integrates source
reports into `docs/source-coverage.md`, decision records into
`docs/decisions.md`, and all status changes into this queue after review.

- [ ] **SRC-PI-001 — Inspect Pi capabilities**
  - Dependencies: none
  - Output: create `docs/sources/pi.md`
  - Ownership: edit only that report; do not edit this queue or the coverage
    matrix
  - Cover: observed version, local session format, stable IDs, incremental
    cursor, usage fields, prompt visibility, automation/execution support,
    retention, and known overlap with provider records
  - Acceptance: every claim cites an observed command, schema, API document, or
    explicit unavailable/unknown result; private payloads and credentials remain
    outside git
  - Verify: `git diff --check`; manually check that no private session content,
    prompt text, tokens, or credentials are present

- [ ] **SRC-HERMES-001 — Inspect Hermes capabilities**
  - Dependencies: none
  - Output: create `docs/sources/hermes.md`
  - Ownership: edit only that report; do not edit this queue or the coverage
    matrix
  - Cover and acceptance: same evidence/field/privacy contract as
    `SRC-PI-001`, including profile/session stores and supported automation
    surfaces
  - Verify: `git diff --check`; privacy review of the complete diff

- [ ] **SRC-CODEX-001 — Inspect Codex capabilities**
  - Dependencies: none
  - Output: create `docs/sources/codex.md`
  - Ownership: edit only that report; do not edit this queue or the coverage
    matrix
  - Cover and acceptance: same evidence/field/privacy contract as
    `SRC-PI-001`, plus installed support for history, `account/usage/read`,
    rate limits, active thread usage, and accessible prompt metadata
  - Verify: `git diff --check`; privacy review of the complete diff

- [ ] **SRC-OPENROUTER-001 — Inspect OpenRouter capabilities**
  - Dependencies: none
  - Output: create `docs/sources/openrouter.md`
  - Ownership: edit only that report; do not edit this queue or the coverage
    matrix
  - Cover and acceptance: same evidence/field/privacy contract as
    `SRC-PI-001`, plus usage, actual charges, classifications, retention, and
    request IDs needed to reconcile provider and harness observations
  - Verify: `git diff --check`; privacy review of the complete diff

- [ ] **FND-001 — Record application foundation defaults**
  - Dependencies: none
  - Plan: Task 1 in the
    [foundation plan](plans/2026-09-07-application-foundation.md)
  - Output: create `docs/decisions/0001-application-foundation.md` with
    the selected backend, ORM/migrations, SvelteKit/npm tooling, API version
    boundary, exact `sv` scaffold version, and API/future-worker processes
  - Ownership: edit only that ADR; do not edit the plan, this queue, or
    `docs/decisions.md`
  - Acceptance: all later foundation tasks have one unambiguous toolchain and
    path layout; data/recovery decisions remain in `DEP-001` and serving
    decisions in `DEP-002`
  - Verify: `git diff --check`

- [ ] **DEP-001 — Decide the private data and recovery boundary**
  - Dependencies: none
  - Output: create `docs/decisions/0002-data-recovery.md` with the
    data-root default/override, `BENCHWARMER_DATA_ROOT` behavior, retention
    boundary, and coordinated database/artifact backup and restore
  - Ownership: edit only that ADR; do not edit this queue or
    `docs/decisions.md`
  - Acceptance: recovery preserves database/artifact consistency and secrets
    stay external
  - Verify: `git diff --check`; the ADR specifies the disposable prototype
    (temporary SQLite file + temporary artifact directory plus exact
    backup/restore/verify commands) that `FND-003` and `QA-004` implement and
    execute

- [ ] **DEP-002 — Decide private serving and supervision**
  - Dependencies: none
  - Output: create `docs/decisions/0003-serving-supervision.md` with
    loopback bindings, Tailscale routing, frontend deployment adapter, process
    supervision, and trusted-proxy assumptions
  - Ownership: edit only that ADR; do not edit this queue or
    `docs/decisions.md`
  - Compare: `adapter-static` behind the chosen static/proxy boundary versus
    `adapter-node`; prefer the static build unless a concrete SSR or Node
    runtime requirement justifies another supervised process
  - Acceptance: the design exposes no unauthenticated non-loopback service and
    names real health/restart behavior for each process
  - Verify: `git diff --check`; validate proposed Tailscale and supervisor
    commands on the target host before marking Done

- [ ] **SRC-001 — Synthesize the source coverage matrix**
  - Dependencies: `SRC-PI-001`, `SRC-HERMES-001`, `SRC-CODEX-001`,
    `SRC-OPENROUTER-001`
  - Output: create `docs/source-coverage.md` comparing observed coverage,
    overlap, missing fields, execution support, and reconciliation identifiers
  - Coordinator: review all four reports, create the matrix, and apply their
    status transitions to this queue in one integration change
  - Acceptance: the matrix links to source reports, preserves
    conflicting/unknown evidence, and does not choose an adapter
  - Verify: `git diff --check`; cross-check every matrix cell against its
    report

- [ ] **SRC-002 — Select the first import adapter**
  - Dependencies: `SRC-001`
  - Output: create `docs/decisions/0004-first-import-adapter.md` with the
    selected source and evidence-based rationale; add adapter-specific
    implementation tasks through the coordinator
  - Acceptance: source exposes stable identity and an incremental/idempotent
    import strategy; unsupported fields remain explicit
  - Verify: trace the proposed cursor and duplicate key against sanitized
    examples

- [ ] **DEC-001 — Integrate the initial decision records**
  - Dependencies: `FND-001`, `DEP-001`, `DEP-002`
  - Output: review the three ADRs together, resolve contradictions, update
    `docs/decisions.md`, update the foundation plan where accepted choices
    differ from its proposed defaults, and apply TODO transitions in one
    coordinator commit
  - Acceptance: each accepted choice links to its ADR; conflicts are resolved
    explicitly rather than hidden in implementation
  - Verify: `git diff --check`; verify all ADR links resolve

- [ ] **FND-002 — Add Python test and lint tooling**
  - Dependencies: `DEC-001`
  - Plan: Task 2 in the foundation plan
  - Verify: `uv sync --dev`; `uv run pytest`; `uv run ruff check .`;
    `uv run ruff format --check .`; `uv run python -m compileall src`

- [ ] **FND-003 — Implement private data-root configuration**
  - Dependencies: `FND-002`, `DEC-001`
  - Plan: Task 3 in the foundation plan
  - Verify: focused config tests plus all `FND-002` checks

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

- [ ] **FND-008 — Report the real database revision in health**
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

- [ ] **UI-001 — Scaffold SvelteKit with the selected adapter and checks**
  - Dependencies: `DEC-001`
  - Plan: Task 11 in the foundation plan
  - Verify from `web/`: `npm run check`; `npm run lint`;
    `npm run test:unit -- --run`; `npm run build`

- [ ] **UI-002 — Build the responsive application shell**
  - Dependencies: `UI-001`
  - Plan: Task 12 in the foundation plan
  - Verify: frontend checks, 375px/desktop inspection, and keyboard navigation

- [ ] **UI-003 — Add the first useful home page**
  - Dependencies: `UI-002`, `UI-004`
  - Plan: Task 14 in the foundation plan
  - Verify: loading/healthy/unmigrated/error UI tests and frontend checks

- [ ] **UI-004 — Add the typed API client and `/api` proxy**
  - Dependencies: `UI-001`
  - Plan: Task 13 in the foundation plan
  - Verify: client tests, frontend checks, and a development-proxy inspection

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

## Backlog

Items remain milestone-sized until their prerequisites make exact
decomposition possible. Decompose one into handoff-ready IDs before
implementation.

- [ ] **ACT-001 — Implement the first idempotent incremental importer**
  - Dependencies: `SRC-002`, `FND-010`, `QA-004`
- [ ] **ACT-002 — Deliver activity totals, filters, freshness, and session
  detail**
  - Dependencies: `ACT-001`
- [ ] **REV-001 — Add ratings, labels, notes, and annotation revision history**
  - Dependencies: `ACT-002`
- [ ] **ACT-003 — Add a second source adapter**
  - Dependencies: `ACT-001`
  - Promotion requirement: the coordinator names the exact second-source task
    ID and inspection report dependency before implementation
- [ ] **REC-001 — Reconcile overlapping harness/provider observations**
  - Dependencies: `ACT-003`
- [ ] **REC-002 — Expose gaps and reconciliation decisions in API and UI**
  - Dependencies: `REC-001`
- [ ] **EVD-001 — Add trusted external evidence with immutable revisions**
  - Dependencies: `ACT-002`, `REV-001`
- [ ] **MOD-001 — Add model/configuration evidence views**
  - Dependencies: `ACT-002`, `EVD-001`
- [ ] **TSK-001 — Prepare and version tasks from imported sessions**
  - Dependencies: `REV-001`
  - Promotion requirement: the coordinator names the first task-family and
    reconstruction decision IDs before implementation
- [ ] **EXP-001 — Build the experiment safety substrate**
  - Dependencies: `TSK-001`
  - Scope: disposable workspaces, fixed scripts, capability checks, credential
    and network policy, budgets, cancellation, durable progress, attempt
    reservation, outcome-unknown reconciliation, and duplicate-paid-work
    protection
  - Promotion requirement: no real or paid trial may be dispatched before this
    task is complete
- [ ] **EXP-002 — Run native harness and compatible direct-API trials**
  - Dependencies: `EXP-001`
  - Promotion requirement: the coordinator names harness, permission, and
    budget decision IDs before implementation
- [ ] **EXP-003 — Compare criterion-level quality and economics per trial**
  - Dependencies: `EXP-002`
- [ ] **EXP-004 — Add controlled comparisons with explicit overrides**
  - Dependencies: `EXP-003`
  - Promotion requirement: the coordinator adds a controlled-comparison
    decision task ID before implementation
- [ ] **SUITE-001 — Promote useful tasks into repeatable evaluation suites**
  - Dependencies: `EXP-003`
- [ ] **EXPORT-001 — Add deliberately sanitized exports and portable reports**
  - Dependencies: `EXP-003`
  - Promotion requirement: the coordinator adds stable-schema and privacy
    review task IDs before implementation

## Done

- [x] **PLAN-001 — Define the local app direction and evaluation semantics**
  - Tailscale access, mobile UI, private snapshots, usage aggregation, harness
    dimensions, native configurations, and system-prompt provenance documented
- [x] **PLAN-002 — Create the buildout roadmap and first agent handoff plan**
  - Milestone dependencies, acceptance gates, task IDs, exact foundation
    paths, and verification commands documented
