# Design decisions

Independently authored proposals live under [decisions/](decisions/README.md).
This document remains the canonical summary after a coordinating task reviews
and integrates those records.

The product direction is agreed: a local SQLite/Svelte app with a Python backend,
personal session review, consolidated usage, trusted external evidence and task
simulations. Harness and system prompts are explicit dimensions; direct Python
API execution is a harness.

## Confirmed starting choices

- **Application foundation:** Use FastAPI/Uvicorn, synchronous SQLAlchemy 2 with
  explicit Alembic migrations, and a TypeScript SvelteKit client under `web/`.
  JSON routes live under `/api/v1`; Python remains authoritative for domain
  rules and persistence. Pin Svelte CLI `0.17.0` and npm's lockfile. See
  [ADR 0001](decisions/0001-application-foundation.md).
- **Access:** Build the frontend with `adapter-static` and a `200.html` fallback,
  then serve it and `/api/v1` from one loopback-only Python process. Use private
  Tailscale Serve HTTPS and Docker Compose restart supervision. Live target-host
  checks remain `DEP-003`. See
  [ADR 0003](decisions/0003-serving-supervision.md).
- **Session storage:** Keep private source snapshots plus normalized metadata
  beneath a configurable root outside the checkout. The database, artifacts,
  and snapshots are durable; jobs, logs, and locks are transient. Back up SQLite
  through its Online Backup API under an application write gate, with manifested
  artifacts and staged restore. See
  [ADR 0002](decisions/0002-data-recovery.md).
- **SQLite safety:** WAL is prohibited unless the process-linked SQLite includes
  the WAL-reset fix: `3.51.3+`, `3.50.7+` on the 3.50 branch, or `3.44.6+` on the
  3.44 branch. `ENV-001` provisions and pins a passing runtime.
- **Experiments:** Start with native harness configurations, capturing accessible
  system prompts, tools, skills and differences. Controlled comparisons remain
  a later capability, rather than an initial requirement.

## Before the first implementation slice

### Initial import source

- **Why it matters:** Determines the first usable slice and real schema
  constraints.
- **Proposed starting point:** Inspect Pi, Hermes, Codex, and provider coverage,
  then choose the richest accessible session source.

### WAL-safe runtime

- **Why it matters:** At M0 review on 2026-09-08, the project virtual
  environment linked vulnerable SQLite `3.50.4`; opening a multi-connection WAL
  database would risk the upstream WAL-reset corruption race.
- **Required next step:** `ENV-001` pins a fixed runtime and implements an
  in-process, pre-connection gate before database migration work begins.

The completed [source coverage matrix](source-coverage.md) records stable IDs,
incremental-import options, token/cost granularity, prompt visibility, execution
surfaces, retention uncertainty, and reconciliation limits. `SRC-002` must choose
from that evidence without converting unavailable or unknown coverage into zero.

## Before the first simulation

### First task family

- **Why it matters:** Coding, research, and text tasks need different fixtures
  and tools.
- **Proposed starting point:** Select representative everyday tasks after
  inspecting sessions.

### First execution harness

- **Why it matters:** Establishes process control and capture requirements.
- **Proposed starting point:** Use Pi or Hermes based on supported automation,
  with a direct API baseline where capabilities fit.

### Reconstruction threshold

- **Why it matters:** Transcripts may lack starting files or external state.
- **Proposed starting point:** Require reviewed inputs and fixtures, with
  approximations labeled before a sweep.

### Scope and budget of broad sweeps

- **Why it matters:** Cheap calls multiply across tasks and retries.
- **Proposed starting point:** Require explicit count/time limits and a total
  spend policy; never run unbounded work on import.

### Meaning of good enough

- **Why it matters:** Enables useful comparison without a universal score.
- **Proposed starting point:** Use task-specific human criteria and notes, then
  verifiable checks.

A direct API baseline cannot replace a tool-using harness on tasks that require
it, even when both are represented through the same experiment interface.

## Can wait until the relevant feature

- Initial external evaluation sources and their APIs, exports or permitted snapshots.
- Annotation scales, blind comparison and review ordering.
- Controlled comparison support: prompt overrides, tool/capability alignment,
  fixed variables and disclosure of remaining differences between harnesses.
- Historical pricing sources and optional API-equivalent subscription estimates.
  Keep actual charges and estimates separate from the beginning.
- Retention durations, attachment limits and selective raw-content deletion.
- Which simulations warrant promotion into named evaluation suites.
- Deterministic graders, judge calibration, portable reports and sanitized exports.
- Repository visibility/license verification before distributing third-party
  fixtures or source material. Public code does not make personal data public.

Implementation tasks live in [TODO.md](TODO.md). This document records choices
and rationale rather than duplicating execution status.
