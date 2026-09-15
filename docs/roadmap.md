# Buildout roadmap

This roadmap turns the product direction in [architecture.md](architecture.md)
into bounded delivery slices. It describes sequence and handoff rules;
architecture rationale stays in the design documents and live task status stays
in [TODO.md](TODO.md).

## Delivery principles

- Prioritize collect → normalize → enrich → discover → select → evaluate. The
  first useful release is a conversation library, not a usage dashboard.
  [conversation-library.md](conversation-library.md) defines the approved scope.
- Keep automatic source import separate from explicitly approved model work,
  including embeddings and judges. Collection growth never expands an approval.
- Resolve cross-machine collection through `COL-001`; do not assume local source
  availability. Shared contracts and synthetic fixtures can proceed meanwhile.

- Deliver vertical slices that leave a usable, testable path through storage,
  API, and UI instead of completing every layer in isolation.
- Keep the Python service authoritative for domain rules, persistence, imports,
  reconciliation, annotations, and experiment control. The SvelteKit
  application is a typed client and presentation layer; it must not open the
  application SQLite database or duplicate domain policy.
- Keep browser-to-service requests under a same-origin `/api` boundary.
  Development may proxy that path to the Python process. Production routing is
  decided by `DEP-002` before deployment.
- Develop only with sanitized fixtures. Private databases, session snapshots,
  prompts, annotations, and generated artifacts stay outside the checkout.
- Preserve source observations before normalization. Unknown, unavailable, and
  unreconciled values remain explicit in API responses and UI states.
- Treat mobile layouts, accessibility, migrations, idempotency, and restart
  behavior as acceptance criteria rather than later cleanup.

## Workstreams and dependencies

```text
four source inspections
  └─► SRC-001 coverage matrix ──► SRC-002 first adapter choice ─────────┐
                                                                        │
three decision proposals ──► DEC-001 decision integration               │
  ├─► FND-002 ──► ENV-001 ──► FND-003..FND-010                         │
  └─► UI-001..UI-005                                                     ┼─► QA
                                                                        │
QA-001..QA-004 foundation verification ─────────────────────────────────┘
  └─► DEP-003 target-host deployment and verification

PLAN-003 ──► LIB-001 shared conversations + ENR-001 approval contract
COL-001 user planning ──► COL-002 cross-machine collection
LIB-001 + foundation ──► ACT-001 Hermes import ──► ACT-002 browse/text search
                                             ├─► REV-001 annotations
                                             ├─► ACT-003 second source
                                             └─► ACT-004 remaining target source

ACT-002 + ENR-001 ──► ENR-002 durable bounded model work ──► ENR-003 enrichment
                                                          └─► SEARCH-001 semantic
ACT-002 ──► DATA-001 collections/datasets ──► DATA-002 private query/export
                    └─► TSK-001 units ──► EXP-001 safety ──► EXP-002 judged trials

Useful library/evaluations ──► RPT-001 reporting + EVD-001 evidence + MOD-001 views
```

The four source inspections can run in parallel because each writes a distinct
`docs/sources/<name>.md` file. The initial decision proposals can also run in
parallel because they write `docs/decisions/0001-*.md` through `0003-*.md`.
`SRC-001` and `DEC-001` are coordinator-owned integration tasks: they combine
reports, update the canonical summaries, and move TODO items after review.

`DEC-001` blocks foundation implementation that relies on the three decision
records. `SRC-002` blocks source-specific schema and importer work, but it does
not block the fixture-backed application foundation.

## Milestones and gates

### M0 — Decisions and feasibility

**Outcome:** Agents can implement without inventing source capabilities,
process boundaries, or storage locations.

- `SRC-PI-001`, `SRC-HERMES-001`, `SRC-CODEX-001`, and
  `SRC-OPENROUTER-001`: inspect one source each and write an independent report
  under `docs/sources/` from observed versions and interfaces.
- `SRC-001`: synthesize the independent reports into
  `docs/source-coverage.md`.
- `SRC-002`: select the first import adapter using the completed matrix.
- `FND-001`: record the backend, migration, frontend, package-manager, and
  worker defaults in `docs/decisions/0001-application-foundation.md`.
- `DEP-001`: decide the private data root and coordinated backup/restore
  contract in `docs/decisions/0002-data-recovery.md`.
- `DEP-002`: decide process binding, supervision, and Tailscale routing in
  `docs/decisions/0003-serving-supervision.md` before deployment work.
- `DEC-001`: reconcile those three proposals, update `docs/decisions.md`, and
  apply their TODO status transitions in a coordinator-owned commit.

**Gate:** Every selected capability has evidence, unknowns remain labeled, and
the first adapter has stable identifiers plus a viable incremental-import
strategy.

Import and trial recovery deliberately have different semantics. An import may
retry after its idempotency key/cursor is durably recorded. A paid trial
reserves an attempt before execution and may enter `outcome_unknown`; recovery
must require reconciliation rather than assuming the request is safe to repeat.

### M1 — Fixture-backed application foundation

**Outcome:** A local developer can migrate a disposable database, start the
Python API and SvelteKit UI, and see typed source/import status from sanitized
fixtures.

The executable plan is
[plans/2026-09-07-application-foundation.md](plans/2026-09-07-application-foundation.md).
It includes Python and frontend checks, truthful health/migration reporting,
the first source/import migrations, responsive navigation, API error states,
browser tests, and restart persistence.

- `ENV-001`: pin a Python/runtime mechanism with a fixed SQLite library and an
  executable pre-connection WAL gate after `FND-002` and before `FND-003`.
- `DEP-003`: implement the private deployment and execute ADR 0003's target-host
  checks after `QA-004`; this blocks operational rollout, not fixture-backed
  implementation.

**Gate:** A fresh checkout resolves a WAL-safe SQLite runtime and passes all
documented checks; no runtime data lands in git; stopping and restarting the API
preserves fixture-backed records. The stateless frontend may restart
independently and has no persistence role.

### M1a: Conversation and approval contracts

**Outcome:** Synthetic conversations retain shared structure across sources;
model-work previews require exact bounded approval without executing anything.

- `LIB-001`: shared conversation v1, strict serialization, provenance, branches,
  tool/artifact references, and synthetic Pi/Hermes/Codex examples.
- `ENR-001`: immutable batch plans, request/resource/cost ceilings, and approval
  invalidation when inputs, models, judges, limits, or disclosure scope change.
- `COL-001`: clarify cross-machine collection with the user and record an accepted
  design before any transport implementation.

The independent contract lanes can run before the remaining database/API work.
Use [plans/2026-09-15-conversation-contracts.md](plans/2026-09-15-conversation-contracts.md).

**Gate:** Positive/negative synthetic tests pass; no private source reads, model
calls, live transport, or durable-execution claims. This is a prerequisite slice,
not the first operational service.

### M2: First useful conversation library

**Outcome:** One real source imports incrementally without duplicates and its
conversations can be found and read from phone or desktop.

- `ACT-001`: map the first adapter into the shared conversation contract and
  retained native snapshots, then validate against an approved private source.
- `ACT-002`: readable transcripts, branches/continuations, filters, keyword and
  metadata search, source freshness, and explicit coverage gaps. Usage/cost
  metadata is available without detailed reporting.
- `REV-001`: durable ratings, labels, notes, and revision history.
- `COL-002`: implement the cross-machine collection path after `COL-001`, with
  enrollment, bounded backfill, offline catch-up, and durable acknowledgments.

**Gate:** Re-import/re-delivery does not duplicate conversations; source-native
snapshots and normalized branches survive restart; search opens relevant evidence;
ratings survive restart; costs cite price evidence or state unavailability. The
cross-machine service is operational only after its own transport/security tests
and `DEP-003`, not because a local importer works.

### M3 — Consolidation proof

**Outcome:** A second source proves the normalized conversation contract is not
Hermes-specific; the remaining target adapter brings Pi, Codex, and Hermes into
the library with explicitly different coverage.

- `ACT-003`: import a second source while preserving its native structure.
- `ACT-004`: import the remaining Pi/Codex/Hermes source after refreshed evidence.
  The source inspection reports are dated observations, not current inventory.
- `REC-001`: link overlapping harness/provider observations without deleting
  either source record.
- `REC-002`: expose unmatched records, overlap decisions, and reconciliation
  differences in API and UI.

**Gate:** Consolidated totals exclude known overlap, account-only totals are
not invented at session scope, and reconciliation is inspectable.

### M4: Enrichment, discovery and reusable datasets

**Outcome:** Approved model work improves discovery; selected conversations are
usable in ad hoc evaluation projects without UI automation.

- `ENR-002`: durable bounded model-work service with approval previews, disclosure
  checks, spend/request reservations, cancellation, and uncertain-outcome recovery.
- `ENR-003`: first description/classification batch with task-specific model tiers,
  revisions, evidence, and cost. Wider metadata stays in explicit bounded follow-ups.
- `SEARCH-001`: approved semantic indexing/query actions alongside text/filter
  fallback; visible stale, incomplete, pending, and unsupported content states.
- `DATA-001`: projects, live saved queries, and frozen revision-pinned datasets.
- `DATA-002`: versioned private read/query/export access for scripts and notebooks.

**Gate:** Imports/search never silently call a model; changed plans need new
approval; dataset membership and revisions reproduce a selection; search hits
link to evidence. Private export is not mislabeled as sanitized public data.

### M5 — Task preparation and safe experiments

**Outcome:** A reviewed task derived from actual work cannot enter a paid or
tool-capable trial until its execution safety substrate exists.

- `TSK-001`: derive meaningful single-response/action or short fixed-sequence units
  from frozen datasets without leaking original answers or later workspace state.
  Preserve segmentation provenance and correlated source lineage.
- `EXP-001`: add disposable workspaces, fixed scripts, capability checks,
  credential/network policy, budgets, cancellation, durable progress, attempt
  reservation, outcome-unknown reconciliation, and duplicate-paid-work
  protection.
- `EXP-002`: implement one native harness adapter and direct Python API
  execution where the task capability permits it. Real and paid trials are
  blocked until `EXP-001` is complete.
- `JDG-001`: configure applied judges, pin rubrics, reserve judgment budget, and
  distinguish judge failure from candidate failure. `EXP-002` includes automatic
  judging under the same approval rather than making it a later optional add-on.
- `EXP-003`: criterion-level review, judge disagreements, and per-trial comparison.

**Gate:** Requested and observed configurations are distinguishable; every
attempt is retained; tool-capable trials use disposable fixtures; recovery
never silently repeats a paid attempt.

### M6: Deeper evaluation and supporting reports

- `SIM-001`: later adaptive user continuation, with allowed knowledge, simulator
  provenance/cost, leakage checks, and separately labeled results.
- `SUITE-001`: reusable evaluation suites built from useful task units.
- `RPT-001`: detailed usage/economics reporting over reconciled metadata.
- `EVD-001` and `MOD-001`: trusted external evaluations and model views, preserving
  dates, revisions, identity uncertainty, and unlike measurements.

These capabilities do not block the useful library. No combined winner score.

## Application map

The route map is a planning contract, not a requirement to create empty pages.
Routes land with the milestone that makes them useful.

| Route | Milestone | Purpose |
| --- | --- | --- |
| `/` | M1/M2 | Source status initially, then recent conversations and discovery |
| `/sources` | M1 | Source coverage and import status |
| `/sessions` | M2/M4 | Conversation list, text/metadata and later semantic search |
| `/sessions/[id]` | M2 | Readable transcript, branches, source evidence and review |
| `/projects` | M4 | Questions, live collections and frozen datasets |
| `/enrichment` | M4 | Bounded previews, approvals, progress and metadata coverage |
| `/evidence` | M6 | Trusted external evaluations and revisions |
| `/models/[id]` | M6 | Model/configuration evidence |
| `/tasks` | M5 | Reviewable task drafts and versions |
| `/experiments` | M5 | Experiment queue, progress, and budgets |
| `/experiments/[id]` | M5 | Trial review and economics |

On narrow screens, use cards or switchable detail views instead of shrinking
wide tables. Navigation, filters, annotations, progress, and comparison
controls must be keyboard accessible and touch friendly.

## Agent handoff protocol

1. Read `AGENTS.md`, [architecture.md](architecture.md),
   [experiments.md](experiments.md), [decisions.md](decisions.md), this
   roadmap, and [TODO.md](TODO.md).
2. Ask the coordinating agent to assign one task ID from **Up Next** whose
   dependencies are complete. The coordinator records exactly one claim line:

   ```markdown
   - Claim: owner `agent:<name-or-session>`, branch `task/<id>-<slug>`,
     started `YYYY-MM-DDTHH:mm:ssZ`
   ```

   The coordinator moves only that task to **In Progress**; research, decision,
   and implementation subagents do not edit [TODO.md](TODO.md) status directly.
   Parallel workers receive disjoint output files. Integration tasks alone
   update shared summaries and the task queue.
3. If a required decision is unresolved, complete its decision task or stop
   with a precise question. Do not hide a product choice inside implementation.
4. Work on a branch or worktree. Keep private inputs and runtime state outside
   the checkout. Add sanitized fixtures only when they are intentionally
   public.
5. Follow the linked task plan. Update the plan when reality invalidates a
   command, file path, or acceptance condition rather than relying on chat
   context.
6. Run the task checks and the repository-wide checks. Record actual command
   results in the PR; do not put transient logs in the repository.
7. Return control to the coordinator for review and status transition. Move
   the task to **Done** only after its acceptance criteria pass. Add newly
   discovered work to **Up Next** or **Backlog** with a unique ID and
   dependency.

A task is handoff-ready only when it names exact files or discovery outputs,
dependencies, acceptance criteria, and verification commands. Multi-day epics
stay in this roadmap and are decomposed into task IDs before implementation.
