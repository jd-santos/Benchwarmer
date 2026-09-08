# Buildout roadmap

This roadmap turns the product direction in [architecture.md](architecture.md)
into bounded delivery slices. It describes sequence and handoff rules;
architecture rationale stays in the design documents and live task status stays
in [TODO.md](TODO.md).

## Delivery principles

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

ACT-001 first import ──► ACT-002 activity UI ──► REV-001 annotations
          │
          └────────────► ACT-003 second source + reconciliation

ACT/REV usable ──► EVD-001 trusted evidence ──► MOD-001 model views
ACT/REV usable ──► TSK-001 task preparation ──► EXP-001 safety substrate
                                                    └─► EXP-002 trials
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
- `ENV-001`: pin a Python/runtime mechanism with a fixed SQLite library and an
  executable pre-connection WAL gate before migration plumbing begins.
- `DEP-003`: execute ADR 0003's deployment checks on the target host after the
  foundation is verified; this blocks operational rollout, not fixture-backed
  implementation.

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

**Gate:** A fresh checkout resolves a WAL-safe SQLite runtime and passes all
documented checks; no runtime data lands in git; stopping and restarting the API
preserves fixture-backed records. The stateless frontend may restart
independently and has no persistence role.

### M2 — First useful activity slice

**Outcome:** One real source imports incrementally without duplicates and is
useful from a phone or desktop.

- `ACT-001`: implement the first source adapter against sanitized fixtures,
  then validate it against a private local source.
- `ACT-002`: add activity totals, filters, source freshness, session list, and
  session detail with explicit coverage gaps.
- `REV-001`: add durable ratings, labels, notes, and revision history.

**Gate:** Re-importing unchanged data creates no duplicate sessions or usage;
ratings survive restart; costs cite a price snapshot or state that no estimate
is available.

### M3 — Consolidation proof

**Outcome:** A second source proves that aggregation and reconciliation are
real, not assumptions embedded in the first adapter.

- `ACT-003`: import a second source while preserving its raw observations.
- `REC-001`: link overlapping harness/provider observations without deleting
  either source record.
- `REC-002`: expose unmatched records, overlap decisions, and reconciliation
  differences in API and UI.

**Gate:** Consolidated totals exclude known overlap, account-only totals are
not invented at session scope, and reconciliation is inspectable.

### M4 — Trusted evidence and model views

**Outcome:** Saved external evaluations and personal evidence can be reviewed
without forcing unlike measurements into one ranking.

- `EVD-001`: save links, provenance, dates, notes, revisions, and permitted
  structured results.
- `MOD-001`: connect activity, personal review, trials, and saved evidence for
  a model/configuration while preserving identity uncertainty.

**Gate:** Revisions are immutable, missing configuration remains unknown, and
no cross-benchmark winner score is produced.

### M5 — Task preparation and safe experiments

**Outcome:** A reviewed task derived from actual work cannot enter a paid or
tool-capable trial until its execution safety substrate exists.

- `TSK-001`: derive and version tasks without leaking original answers or later
  workspace state.
- `EXP-001`: add disposable workspaces, fixed scripts, capability checks,
  credential/network policy, budgets, cancellation, durable progress, attempt
  reservation, outcome-unknown reconciliation, and duplicate-paid-work
  protection.
- `EXP-002`: implement one native harness adapter and direct Python API
  execution where the task capability permits it. Real and paid trials are
  blocked until `EXP-001` is complete.
- `EXP-003`: add criterion-level review and per-trial comparison.

**Gate:** Requested and observed configurations are distinguishable; every
attempt is retained; tool-capable trials use disposable fixtures; recovery
never silently repeats a paid attempt.

## Application map

The route map is a planning contract, not a requirement to create empty pages.
Routes land with the milestone that makes them useful.

| Route | Milestone | Purpose |
| --- | --- | --- |
| `/` | M1/M2 | Activity summary and source freshness |
| `/sources` | M1 | Source coverage and import status |
| `/sessions` | M2 | Filterable session and usage list |
| `/sessions/[id]` | M2 | Session evidence and review |
| `/evidence` | M4 | Trusted external evaluations and revisions |
| `/models/[id]` | M4 | Model/configuration evidence |
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
